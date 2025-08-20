import asyncio
import discord
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
from bson.timestamp import Timestamp  

class BanManager:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database_manager
        self.auto_unban_task = None
        self.embed_builder = bot.embed_builder
        self.punishment_channel_id = int(bot.config['channels']['punishments'])
        

    def parse_duration(self, duration_str: str) -> int:
        if not isinstance(duration_str, str):
            raise ValueError(f"Duration must be a string, got {type(duration_str).__name__}")
            
        pattern = re.compile(r'^(\d+)([smhd])$')
        match = pattern.match(duration_str.lower())
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}. Use format like '1s', '1h', '1d', '1m'")

        amount = int(match.group(1))
        unit = match.group(2)
        current_time = int(datetime.now().timestamp())
        delta = None

        if unit == 's':
            delta = timedelta(seconds=amount)
        elif unit == 'm':
            delta = timedelta(minutes=amount)
        elif unit == 'h':
            delta = timedelta(hours=amount)
        elif unit == 'd':
            delta = timedelta(days=amount)

        return current_time + int(delta.total_seconds())

    async def start_auto_unban(self):
        if self.auto_unban_task is None:
            self.auto_unban_task = asyncio.create_task(self._auto_unban_loop())

    async def stop_auto_unban(self):
        if self.auto_unban_task:
            self.auto_unban_task.cancel()
            self.auto_unban_task = None

    async def _auto_unban_loop(self):
        while True:
            try:
                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                
                banned_users = self.db.find('users', {'banned': True})
                
                for user in banned_users:
                    
                    if 'ban_expiry' in user and user['ban_expiry'] < current_time:
                        await self.unban_user(
                            discord_id=str(user['discordid']),
                            unban_reason="Ban duration expired",
                            unbanned_by="System"
                        )
                    
                await asyncio.sleep(1)  
            except Exception as e:
                self.bot.logger.error(f"Error in auto unban loop: {e}")
                await asyncio.sleep(1)  

    async def ban_user(self, discord_id: str, reason: str, duration: str, staffid: str) -> bool:
        try:
            
            user_data = self.db.find_one('users', {'discordid': str(discord_id)})
            if not user_data:
                raise ValueError(f"User with Discord ID {discord_id} not found in database")
            
            ign = user_data['ign']
            ban_duration = self.parse_duration(duration)
            
            
            update_data = {
                'banned': True,
                'ban_reason': reason,
                'ban_date': Timestamp(int(datetime.now().timestamp()), 1),
                'ban_expiry': Timestamp(ban_duration, 1),
                'ban_staff': str(staffid)
            }
            self.db.update_one('users', {'discordid': str(discord_id)}, {'$set': update_data})

            
            ban_data = {
                'discordid': str(discord_id),
                'ign': ign,
                'reason': reason,
                'date': Timestamp(int(datetime.now().timestamp()), 1),
                'duration': Timestamp(ban_duration, 1),
                'staffid': str(staffid),
                'unbanned': False
            }
            self.db.insert('bans', ban_data)

            
            guild = self.bot.get_guild(int(self.bot.config['bot']['guildid']))
            if not guild:
                raise ValueError("Could not find the configured guild")
                
            member = await guild.fetch_member(int(discord_id))
            if not member:
                raise ValueError(f"Could not find member with ID {discord_id}")
                
            banned_role = guild.get_role(int(self.bot.config['roles']['rankedban']))
            frozen_role = guild.get_role(int(self.bot.config['roles']['frozen']))
            
            if banned_role:
                await member.add_roles(banned_role)
            if frozen_role and frozen_role in member.roles:
                await member.remove_roles(frozen_role)

            
            channel = self.bot.get_channel(self.punishment_channel_id)
            if channel:
                ban_expiry_time = datetime.fromtimestamp(ban_duration).strftime("%Y-%m-%d %H:%M:%S")
                embed = self.embed_builder.build_error(
                    title='Rank Banned',
                    description=f'**User:** <@{discord_id}> ({ign})\n**Reason:** `{reason}`\n**Duration:** `{duration}`\n**Ban expires at:** `{ban_expiry_time}`\n**Staff:** <@{staffid}>\n\nIf you wish to appeal this punishment, please create an appeal Support Channel and staff will be swift to help.'
                )
                embed.set_thumbnail(url='attachment://ban.png')
                with open('asserts/punishments/ban.png', 'rb') as f:
                    file = discord.File(f, filename='ban.png')
                    await channel.send(content=f'<@{discord_id}>', file=file, embed=embed)
            return True
        except Exception as e:
            self.bot.logger.error(f"Error banning user {discord_id}: {e}")
            return False

    async def unban_user(self, discord_id: str, unban_reason: str = "No reason provided", unbanned_by: str = "System") -> bool:
        try:
            
            user_data = self.db.find_one('users', {'discordid': str(discord_id)})
            if not user_data:
                raise ValueError(f"User with Discord ID {discord_id} not found in database")

            
            update_data = {
                'banned': False,
                'ban_reason': user_data.get('ban_reason', ""),  
                'ban_date': user_data.get('ban_date', Timestamp(0, 0)),  
                'ban_expiry': user_data.get('ban_expiry', Timestamp(0, 0)),  
                'ban_staff': user_data.get('ban_staff', ""),  
                'last_unban_reason': unban_reason,
                'last_unbanned_by': unbanned_by,
                'last_unban_date': Timestamp(int(datetime.now().timestamp()), 1)
            }
            result = self.db.update_one('users', {'discordid': str(discord_id)}, {'$set': update_data})

            
            self.db.update_one(
                'bans',
                {'discordid': str(discord_id), 'unbanned': False},
                {
                    '$set': {
                        'unbanned': True,
                        'unbanreason': unban_reason,
                        'unbannedby': unbanned_by,
                        'unbannedate': Timestamp(int(datetime.now().timestamp()), 1)
                    }
                }
            )

            
            guild = self.bot.get_guild(int(self.bot.config['bot']['guildid']))
            if guild:
                member = await guild.fetch_member(int(discord_id))
                if member:
                    banned_role = guild.get_role(int(self.bot.config['roles']['rankedban']))
                    if banned_role and banned_role in member.roles:
                        await member.remove_roles(banned_role)

            if result:
                channel = self.bot.get_channel(self.punishment_channel_id)
                if channel:
                    if(unbanned_by == "System"):
                        embed = self.embed_builder.build_success(
                            title='User Unbanned',
                            description=f'**User:** <@{discord_id}>\n**Reason:** `{unban_reason}`\n**Unbanned by:** {unbanned_by} \n\nIn future if you face another punishment, it will likely increase due to your punishment history.'
                        )
                        embed.set_thumbnail(url='attachment://unbanunmute.png')
                    else:
                        embed = self.embed_builder.build_success(
                            title='User Unbanned',
                            description=f'**User:** <@{discord_id}>\n**Reason:** `{unban_reason}`\n**Unbanned by:** <@{unbanned_by}> \n\nIn future if you face another punishment, it will likely increase due to your punishment history.'
                        )
                        embed.set_thumbnail(url='attachment://unbanunmute.png')
                    with open('asserts/punishments/unbanunmute.png', 'rb') as f:
                        file = discord.File(f, filename='unbanunmute.png')
                        await channel.send(content=f'<@{discord_id}>', file=file, embed=embed)
            return True
        except Exception as e:
            self.bot.logger.error(f"Error unbanning user {discord_id}: {e}")
            return False

    async def is_banned(self, discord_id: str) -> Optional[Dict[str, Any]]:
        try:
            current_time = Timestamp(int(datetime.now().timestamp()), 1)
            user_data = self.db.find_one('users', {
                'discordid': str(discord_id),
                'banned': True,
                'ban_expiry': {'$gt': current_time}
            })
            if user_data and user_data.get('banned'):
                return {
                    'discordid': user_data['discordid'],
                    'reason': user_data.get('ban_reason'),
                    'duration': user_data.get('ban_expiry'),
                    'staffid': user_data.get('ban_staff')
                }
            return None
        except Exception as e:
            self.bot.logger.error(f"Error checking ban status for {discord_id}: {e}")
            return None

    async def get_ban_info(self, discord_id: str) -> Optional[Dict[str, Any]]:
        try:
            user_data = self.db.find_one('users', {'discordid': str(discord_id)})
            if user_data and user_data.get('banned'):
                return {
                    'discordid': user_data['discordid'],
                    'reason': user_data.get('ban_reason'),
                    'date': user_data.get('ban_date'),
                    'duration': user_data.get('ban_expiry'),
                    'staffid': user_data.get('ban_staff'),
                    'unbanned': False
                }
            elif user_data and user_data.get('last_unban_date'):
                return {
                    'discordid': user_data['discordid'],
                    'unbanreason': user_data.get('last_unban_reason'),
                    'unbannedby': user_data.get('last_unbanned_by'),
                    'unbannedate': user_data.get('last_unban_date'),
                    'unbanned': True
                }
            return None
        except Exception as e:
            self.bot.logger.error(f"Error getting ban info for {discord_id}: {e}")
            return None
