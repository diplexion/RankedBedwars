import yaml
import os
from typing import List, Dict, Optional
from managers.database_manager import DatabaseManager
from datetime import datetime
import discord
from bson import Timestamp

class PartyManager:
    def __init__(self, config_file: str = 'configs/config.yml', db_manager: DatabaseManager = None, logger=None):
        self.db_manager = db_manager
        self.logger = logger if logger else print
        self.config = self._load_config(config_file)
        self.inactive_timeout = self.config.get('party', {}).get('inactive_timeout', 1800)
        
        self.autowarp_enabled = True

    def _load_config(self, config_file: str) -> dict:
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as file:
                    config = yaml.safe_load(file) or {}
                    if hasattr(self.logger, 'info'):
                        self.logger.info(f"Successfully loaded config from {config_file}")
                    else:
                        self.logger(f"Successfully loaded config from {config_file}")
                    return config
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to load config from {config_file}: {e}")
            else:
                self.logger(f"Failed to load config from {config_file}: {e}")
        return {}

    def create_party(self, leader_id: str, party_name: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Creating party: leader={leader_id}, party_name={party_name}")
        else:
            self.logger(f"Creating party: leader={leader_id}, party_name={party_name}")
        
        if not self.user_exists(leader_id):
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"User {leader_id} does not exist")
            else:
                self.logger(f"User {leader_id} does not exist")
            return False

        
        existing_party = self.get_party(party_name)
        if existing_party or not self.config.get('party', {}).get('partyenabled', True):
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} already exists or parties are disabled")
            else:
                self.logger(f"Party {party_name} already exists or parties are disabled")
            return False

        party_data = {
            'party_name': party_name,
            'leader': leader_id,
            'members': [leader_id],
            'elo': self.get_player_elo(leader_id) or 0,
            'is_private': True,
            'creation_time': Timestamp(int(datetime.now().timestamp()), 1),
            'last_activity': Timestamp(int(datetime.now().timestamp()), 1)
        }

        try:
            self.db_manager.insert('parties', party_data)
            if hasattr(self.logger, 'info'):
                self.logger.info(f"Successfully created party {party_name}")
            else:
                self.logger(f"Successfully created party {party_name}")
            return True
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to create party {party_name}: {e}")
            else:
                self.logger(f"Failed to create party {party_name}: {e}")
            return False

    def invite_member(self, party_name: str, member_id: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Inviting member {member_id} to party {party_name}")
        else:
            self.logger(f"Inviting member {member_id} to party {party_name}")
        
        if not self.user_exists(member_id):
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"User {member_id} does not exist")
            else:
                self.logger(f"User {member_id} does not exist")
            return False

        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        if member_id not in party['members'] and len(party['members']) < self.config.get('party', {}).get('partysize', 4):
            member_elo = self.get_player_elo(member_id) or 0
            try:
                success = self.db_manager.update_one(
                    'parties',
                    {'party_name': party_name},
                    {
                        '$push': {'members': member_id},
                        '$inc': {'elo': member_elo},
                        '$set': {'last_activity': Timestamp(int(datetime.now().timestamp()), 1)}
                    }
                )
                if success:
                    if hasattr(self.logger, 'info'):
                        self.logger.info(f"Successfully invited {member_id} to party {party_name}")
                    else:
                        self.logger(f"Successfully invited {member_id} to party {party_name}")
                return success
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Failed to update party after invite: {e}")
                else:
                    self.logger(f"Failed to update party after invite: {e}")
                return False
        return False

    def member_join(self, party_name: str, member_id: str) -> bool:
        return self.invite_member(party_name, member_id)

    def kick_member(self, party_name: str, member_id: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Kicking member {member_id} from party {party_name}")
        else:
            self.logger(f"Kicking member {member_id} from party {party_name}")
        
        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        if member_id in party['members'] and member_id != party['leader']:
            member_elo = self.get_player_elo(member_id) or 0
            try:
                success = self.db_manager.update_one(
                    'parties',
                    {'party_name': party_name},
                    {
                        '$pull': {'members': member_id},
                        '$inc': {'elo': -member_elo},
                        '$set': {'last_activity': Timestamp(int(datetime.now().timestamp()), 1)}
                    }
                )
                if success:
                    if hasattr(self.logger, 'info'):
                        self.logger.info(f"Successfully kicked {member_id} from party {party_name}")
                    else:
                        self.logger(f"Successfully kicked {member_id} from party {party_name}")
                    
                    
                    updated_party = self.get_party(party_name)
                    if not updated_party['members']:
                        self.disband_party(party_name)
                    return True
                return False
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Failed to update party after kick: {e}")
                else:
                    self.logger(f"Failed to update party after kick: {e}")
                return False
        return False

    def promote_member(self, party_name: str, member_id: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Promoting member {member_id} to leader in party {party_name}")
        else:
            self.logger(f"Promoting member {member_id} to leader in party {party_name}")
        
        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        if member_id in party['members']:
            try:
                success = self.db_manager.update_one(
                    'parties',
                    {'party_name': party_name},
                    {
                        '$set': {
                            'leader': member_id,
                            'last_activity': Timestamp(int(datetime.now().timestamp()), 1)
                        }
                    }
                )
                if success:
                    if hasattr(self.logger, 'info'):
                        self.logger.info(f"Successfully promoted {member_id} to leader in party {party_name}")
                    else:
                        self.logger(f"Successfully promoted {member_id} to leader in party {party_name}")
                return success
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Failed to promote member in party: {e}")
                else:
                    self.logger(f"Failed to promote member in party: {e}")
                return False
        return False

    def disband_party(self, party_name: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Disbanding party {party_name}")
        else:
            self.logger(f"Disbanding party {party_name}")
        
        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        try:
            success = self.db_manager.delete('parties', {'party_name': party_name})
            if success:
                if hasattr(self.logger, 'info'):
                    self.logger.info(f"Successfully disbanded party {party_name}")
                else:
                    self.logger(f"Successfully disbanded party {party_name}")
            return success
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to disband party: {e}")
            else:
                self.logger(f"Failed to disband party: {e}")
            return False

    def leave_party(self, party_name: str, member_id: str) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Member {member_id} leaving party {party_name}")
        else:
            self.logger(f"Member {member_id} leaving party {party_name}")
        
        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        if member_id in party['members']:
            
            if member_id == party['leader']:
                return self.disband_party(party_name)

            member_elo = self.get_player_elo(member_id) or 0
            try:
                success = self.db_manager.update_one(
                    'parties',
                    {'party_name': party_name},
                    {
                        '$pull': {'members': member_id},
                        '$inc': {'elo': -member_elo},
                        '$set': {'last_activity': Timestamp(int(datetime.now().timestamp()), 1)}
                    }
                )
                if success:
                    if hasattr(self.logger, 'info'):
                        self.logger.info(f"Successfully removed {member_id} from party {party_name}")
                    else:
                        self.logger(f"Successfully removed {member_id} from party {party_name}")

                    
                    updated_party = self.get_party(party_name)
                    if not updated_party['members']:
                        self.disband_party(party_name)
                    return True
                return False
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Failed to update party after leave: {e}")
                else:
                    self.logger(f"Failed to update party after leave: {e}")
                return False
        return False

    def set_party_private(self, party_name: str, is_private: bool) -> bool:
        if hasattr(self.logger, 'info'):
            self.logger.info(f"Setting party {party_name} privacy to {is_private}")
        else:
            self.logger(f"Setting party {party_name} privacy to {is_private}")
        
        party = self.get_party(party_name)
        if not party:
            if hasattr(self.logger, 'warning'):
                self.logger.warning(f"Party {party_name} does not exist")
            else:
                self.logger(f"Party {party_name} does not exist")
            return False

        try:
            success = self.db_manager.update_one(
                'parties',
                {'party_name': party_name},
                {
                    '$set': {
                        'is_private': is_private,
                        'last_activity': Timestamp(int(datetime.now().timestamp()), 1)
                    }
                }
            )
            if success:
                if hasattr(self.logger, 'info'):
                    self.logger.info(f"Successfully updated privacy for party {party_name}")
                else:
                    self.logger(f"Successfully updated privacy for party {party_name}")
            return success
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to update party privacy: {e}")
            else:
                self.logger(f"Failed to update party privacy: {e}")
            return False

    def get_party(self, party_name: str) -> Optional[Dict]:
        if not self.db_manager:
            if hasattr(self.logger, 'warning'):
                self.logger.warning("DatabaseManager not initialized")
            else:
                self.logger("DatabaseManager not initialized")
            return None
            
        return self.db_manager.find_one('parties', {'party_name': str(party_name)})

    def get_party_members(self, party_name: str) -> Optional[List[str]]:
        party = self.get_party(str(party_name))
        return party.get('members') if party else None

    def get_party_size(self, party_name: str) -> Optional[int]:
        party = self.get_party(str(party_name))
        return len(party.get('members', [])) if party else None

    def get_party_leader(self, party_name: str) -> Optional[str]:
        party = self.get_party(str(party_name))
        return party.get('leader') if party else None

    def get_party_elo(self, party_name: str) -> Optional[int]:
        party = self.get_party(str(party_name))
        if party:
            elo = party.get('elo', 0)
            if elo <= self.config.get('party', {}).get('partyelolimit', float('inf')):
                return elo
        return None

    def get_player_elo(self, discord_id: str) -> int:
        if not self.db_manager:
            if hasattr(self.logger, 'warning'):
                self.logger.warning("DatabaseManager not initialized")
            else:
                self.logger("DatabaseManager not initialized")
            return 0
            
        user = self.db_manager.find_one('users', {'discordid': str(discord_id)})
        return user.get('elo', 0) if user else 0

    def update_party_activity(self, party_name: str) -> None:
        try:
            self.db_manager.update_one(
                'parties',
                {'party_name': party_name}, 
                {'$set': {'last_activity': Timestamp(int(datetime.now().timestamp()), 1)}}
            )
        except Exception as e:
            if hasattr(self.logger, 'error'):
                self.logger.error(f"Failed to update party activity: {e}")
            else:
                self.logger(f"Failed to update party activity: {e}")

    async def check_inactive_parties(self) -> None:
        if not self.db_manager:
            self.logger.warning("DatabaseManager not initialized")
            return

        current_time = int(datetime.now().timestamp())
        cutoff_time = current_time - self.inactive_timeout

        inactive_parties = self.db_manager.find('parties', {
            'last_activity': {'$lt': cutoff_time}
        })

        for party in inactive_parties:
            party_name = party.get('party_name')
            self.logger.info(f"Auto-disbanding inactive party {party_name}")
            self.disband_party(party_name)
            
    def is_in_ignore_list(self, user_id: str, target_id: str) -> bool:
        if not self.db_manager:
            return False
            
        user_data = self.db_manager.find_one('users', {'discordid': str(user_id)})
        if not user_data:
            return False
            
        ignore_list = user_data.get('partyingnorelist', [])
        return str(target_id) in ignore_list
        
    def add_to_ignore_list(self, user_id: str, target_id: str) -> bool:
        if not self.db_manager:
            return False
            
        
        if not self.user_exists(user_id):
            return False
            
        
        if self.is_in_ignore_list(user_id, target_id):
            return True  
            
        
        result = self.db_manager.update_one(
            'users',
            {'discordid': str(user_id)},
            {'$addToSet': {'partyingnorelist': str(target_id)}}
        )
        return result
        
    def remove_from_ignore_list(self, user_id: str, target_id: str) -> bool:
        if not self.db_manager:
            return False
            
        
        if not self.user_exists(user_id):
            return False
            
        
        result = self.db_manager.update_one(
            'users',
            {'discordid': str(user_id)},
            {'$pull': {'partyingnorelist': str(target_id)}}
        )
        return result

    def auto_disband(self, party_name: str) -> None:
        party = self.get_party(party_name)
        if party and not party['members']:
            self.disband_party(party_name)

    def user_exists(self, discord_id: str) -> bool:
        if not self.db_manager:
            if hasattr(self.logger, 'warning'):
                self.logger.warning("DatabaseManager not initialized, cannot check if user exists")
            else:
                self.logger("DatabaseManager not initialized, cannot check if user exists")
            return False

        query = {'discordid': str(discord_id)}
        result = self.db_manager.find_one('users', query)
        return result is not None

    def get_party_by_member(self, member_id: str) -> Optional[Dict]:
        if not self.db_manager:
            if hasattr(self.logger, 'warning'):
                self.logger.warning("DatabaseManager not initialized")
            else:
                self.logger("DatabaseManager not initialized")
            return None
            
        return self.db_manager.find_one('parties', {'members': str(member_id)})

    async def handle_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not after.channel or before.channel == after.channel:
            return  

        
        party = self.get_party_by_member(str(member.id))
        if not party or party.get('leader') != str(member.id):
            return  

        
        if not party.get('autopartywarp', False):
            return  

        cant_move = []
        target_channel = after.channel

        
        for member_id in party.get('members', []):
            if member_id == str(member.id):  
                continue

            party_member = member.guild.get_member(int(member_id))
            if party_member:
                try:
                    await party_member.move_to(target_channel)
                except:
                    cant_move.append(party_member.mention)

        
        if cant_move:
            try:
                with open('configs/config.yml', 'r', encoding='utf-8') as file:
                    config = yaml.safe_load(file)
                alerts_channel = member.guild.get_channel(int(config['channels']['alerts']))
                
                if alerts_channel:
                    alert_embed = discord.Embed(
                        title="Party Auto-Warp Failed",
                        description=f"Could not move some party members to {target_channel.mention}",
                        color=discord.Color.yellow()
                    )
                    await alerts_channel.send(
                        content=f"{member.mention} couldn't move: {', '.join(cant_move)}",
                        embed=alert_embed
                    )
            except Exception as e:
                if hasattr(self.logger, 'error'):
                    self.logger.error(f"Failed to send auto-warp alert: {e}")
                else:
                    self.logger(f"Failed to send auto-warp alert: {e}")
