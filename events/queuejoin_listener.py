import discord
import asyncio
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.party_manager import PartyManager
import yaml
import os
from utils.embed_builder import EmbedBuilder  
from managers.queue_processor import QueueProcessor

class QueueJoinListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.party_manager = PartyManager(config_file='configs/config.yml', db_manager=self.database_manager)
        self.config = self.load_config()
        self.embed_builder = EmbedBuilder()  
        
        self._queue_processor = None
        
        
        self.websocket_enabled = self.config.get('websocket', {}).get('enabled', False)
        self.ws_manager = getattr(bot, 'websocket_manager', None) if self.websocket_enabled else None
        self.bot.logger.info(f"QueueJoinListener initialized with WebSocket enabled: {self.websocket_enabled}")

    def load_config(self) -> dict:
        config_path = os.path.join('configs', 'config.yml')
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.bot.logger.error(f"Failed to load configuration: {e}")
            raise

    @property
    def queue_processor(self):
        
        if self._queue_processor is None:
            if self.bot.queue_processor is not None:
                self._queue_processor = self.bot.queue_processor
            else:
                
                self._queue_processor = QueueProcessor(self.bot)
                self.bot.logger.warning("Created temporary QueueProcessor instance in QueueJoinListener")
        return self._queue_processor

    async def move_to_waiting_vc(self, member: discord.Member, reason: str):
        try:
            waiting_vc_id = int(self.config['channels']['waitingvc'])
            waiting_channel = self.bot.get_channel(waiting_vc_id)
            if waiting_channel:
                await member.move_to(waiting_channel)
                
                
                alerts_channel_id = int(self.config['channels']['alerts'])
                alerts_channel = self.bot.get_channel(alerts_channel_id)
                if alerts_channel:
                    await alerts_channel.send(f"Hey {member.mention}, {reason}")
        except Exception as e:
            self.bot.logger.error(f"Failed to move member to waiting VC: {e}")
    
    def has_restricted_role(self, member: discord.Member) -> bool:
        frozen_role_id = int(self.config['roles']['frozen'])
        rankedban_role_id = int(self.config['roles']['rankedban'])
        return any(role.id in [frozen_role_id, rankedban_role_id] for role in member.roles)
        
    def get_player_elo(self, discord_id: int) -> int:
        try:
            player = self.database_manager.find_one('users', {'discordid': str(discord_id)})
            if player and 'elo' in player:
                return int(player['elo'])
            else:
                self.bot.logger.warning(f"Player {discord_id} not found or has no ELO value")
                return 0
        except Exception as e:
            self.bot.logger.error(f"Error getting player ELO for {discord_id}: {e}")
            return 0
            
    async def check_player_online(self, ign: str) -> bool:
        if not self.websocket_enabled or not self.ws_manager:
            
            self.bot.logger.debug(f"WebSocket not enabled, assuming player {ign} is online")
            return True
            
        try:
            
            player_handler = getattr(self.ws_manager, 'player_handler', None)
            if player_handler:
                
                is_online = await asyncio.wait_for(
                    player_handler.check_player_online(ign), 
                    timeout=5.0  
                )
                self.bot.logger.info(f"WebSocket player check for {ign}: {'online' if is_online else 'offline'}")
                return is_online
            else:
                self.bot.logger.warning("WebSocket player_handler not available, assuming player is online")
                return True
        except asyncio.TimeoutError:
            self.bot.logger.warning(f"WebSocket player check timed out for {ign}, assuming player is offline")
            return False
        except Exception as e:
            self.bot.logger.error(f"Error checking player online status: {e}", exc_info=True)
            return False  

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        
        if before.channel:
            old_queue = self.database_manager.find_one('queues', {'channelid': str(before.channel.id)})
            if old_queue:
                
                new_channel_id = after.channel.id if after.channel else None
                
                await self.queue_processor.process_queue_leave(member.id, before.channel.id, new_channel_id)
          
        if after.channel:
            
            try:
                queue = self.database_manager.find_one('queues', {'channelid': str(after.channel.id)})
                if not queue:
                    return
                
                
                is_ranked = not queue.get('iscasual', False)
                queuetype = 'ranked' if is_ranked else 'casual'
                queuestats = self.database_manager.find_one('queuestats', {'queuetype': queuetype})
                if queuestats and not queuestats.get('stats', True):
                    await self.move_to_waiting_vc(member, reason=f"This queue is currently disabled.")
                    return
                
                player = self.database_manager.find_one('users', {'discordid': str(member.id)})
                if not player:
                    await self.move_to_waiting_vc(member, reason="You are not registered. Please register to participate. Maybe `update`?")
                    return
                  
                if not player.get('ign'):
                    await self.move_to_waiting_vc(member, reason="You don't have a valid IGN. Please update your profile.")
                    return
                
                if self.has_restricted_role(member):
                    await self.move_to_waiting_vc(member, reason="You have a restricted role. please contact a staff if you think its an mistake")
                    return

                player_elo = self.get_player_elo(member.id)
                
                
                min_elo = int(queue.get('minelo', 0))
                max_elo = int(queue.get('maxelo', 9999))
                self.bot.logger.info(f"Player {member.id} ELO check: {player_elo} against range {min_elo}-{max_elo}")
                if not (min_elo <= player_elo <= max_elo):
                    await self.move_to_waiting_vc(member, reason=f"Your ELO ({player_elo}) is out of the allowed range for this queue ({min_elo}-{max_elo}).")
                    return
                
                
                if self.websocket_enabled and self.ws_manager:
                    ign = player.get('ign')
                    if ign:
                        is_online = await self.check_player_online(ign)
                        if not is_online:
                            await self.move_to_waiting_vc(member, reason=f"You are not currently online in-game. Please join the Minecraft server before queueing.")
                            return
                        else:
                            self.bot.logger.info(f"Player {ign} is online, allowing queue join")
                
                if self.config['party']['partyenabled']:
                    party = self.party_manager.get_party_by_member(str(member.id))
                    if party:
                        if len(party.get('members', [])) > self.config['party']['partyqueuesize']:
                            await self.move_to_waiting_vc(member, reason="Your party size exceeds the allowed limit for this queue.")
                            return
                        
                        
                        if self.websocket_enabled and self.ws_manager:
                            
                            offline_members = []
                            for party_member_id in party.get('members', []):
                                party_member = self.database_manager.find_one('users', {'discordid': party_member_id})
                                if party_member and 'ign' in party_member:
                                    party_member_ign = party_member['ign']
                                    is_online = await self.check_player_online(party_member_ign)
                                    if not is_online:
                                        offline_members.append(party_member_ign)
                            
                            
                            if offline_members:
                                offline_list = ", ".join([f"`{ign}`" for ign in offline_members])
                                await self.move_to_waiting_vc(
                                    member, 
                                    reason=f"Not all party members are online in-game. Offline members: {offline_list}"
                                )
                                return
                
                await self.queue_processor.process_queue_join(member.id, after.channel.id)

            except Exception as e:
                self.bot.logger.error(f"Error in queue join listener: {e}")

async def setup(bot):
    await bot.add_cog(QueueJoinListener(bot))
