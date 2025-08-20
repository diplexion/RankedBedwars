import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from bson.timestamp import Timestamp
import discord

class MuteManager:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database_manager
        self.auto_unmute_task = None
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

    async def start_auto_unmute(self):
        if self.auto_unmute_task is None:
            self.auto_unmute_task = asyncio.create_task(self._auto_unmute_loop())

    async def stop_auto_unmute(self):
        if self.auto_unmute_task:
            self.auto_unmute_task.cancel()
            self.auto_unmute_task = None

    async def _auto_unmute_loop(self):
        while True:
            try:
                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                expired_mutes = self.db.find('mutes', {
                    'duration': {'$lt': current_time},
                    'unmuted': False
                })
                
                for mute in expired_mutes:
                    await self.unmute_user(
                        discord_id=mute['discordid'],
                        unmute_reason="Mute duration expired",
                        unmuted_by="System"
                    )
                
                await asyncio.sleep(1)  
            except Exception as e:
                self.bot.logger.error(f"Error in auto unmute loop: {e}")
                await asyncio.sleep(1)  

    async def mute_user(self, discord_id: str, reason: str, duration: str, staffid: str) -> bool:
        try:
            user_data = self.db.find_one('users', {'discordid': str(discord_id)})
            if not user_data:
                raise ValueError(f"User with Discord ID {discord_id} not found in database")
            ign = user_data['ign']
            mute_duration = self.parse_duration(duration)
            mute_data = {
                'discordid': str(discord_id),
                'ign': ign,
                'reason': reason,
                'date': Timestamp(int(datetime.now().timestamp()), 1),
                'duration': Timestamp(mute_duration, 1),
                'staffid': str(staffid),
                'unmuted': False
            }
            self.db.insert('mutes', mute_data)
            guild = self.bot.get_guild(int(self.bot.config['bot']['guildid']))
            if not guild:
                raise ValueError("Could not find the configured guild")
            member = await guild.fetch_member(int(discord_id))
            if not member:
                raise ValueError(f"Could not find member with ID {discord_id}")
            muted_role = guild.get_role(int(self.bot.config['roles']['rankedmuted']))
            if muted_role:
                await member.add_roles(muted_role)
            channel = self.bot.get_channel(self.punishment_channel_id)
            if channel:
                mute_expiry_time = datetime.fromtimestamp(mute_duration).strftime("%Y-%m-%d %H:%M:%S")
                embed = self.embed_builder.build_error(
                    title='Muted',
                    description=f'**User:** <@{discord_id}> ({ign})\n**Reason:** `{reason}`\n**Duration:** `{duration}`\n**Mute expires at:** `{mute_expiry_time}`\n**Staff:** <@{staffid}>\n\nIf you wish to appeal this punishment, please create an appeal Support Channel and staff will be swift to help.'
                )
                embed.set_thumbnail(url='attachment://ban.png')
                with open('asserts/punishments/ban.png', 'rb') as f:
                    file = discord.File(f, filename='ban.png')
                    await channel.send(content=f'<@{discord_id}>', file=file, embed=embed)
            return True
        except Exception as e:
            self.bot.logger.error(f"Error muting user {discord_id}: {e}")
            return False

    async def unmute_user(self, discord_id: str, unmute_reason: str = "No reason provided", unmuted_by: str = "System") -> bool:
        try:
            update_data = {
                'unmuted': True,
                'unmutereason': unmute_reason,
                'unmutedby': unmuted_by,
                'unmutedate': Timestamp(int(datetime.now().timestamp()), 1)
            }
            result = self.db.update_one('mutes', {'discordid': str(discord_id), 'unmuted': False}, {'$set': update_data})
            guild = self.bot.get_guild(int(self.bot.config['bot']['guildid']))
            if guild:
                member = await guild.fetch_member(int(discord_id))
                if member:
                    muted_role = guild.get_role(int(self.bot.config['roles']['rankedmuted']))
                    if muted_role and muted_role in member.roles:
                        await member.remove_roles(muted_role)
            if result:
                channel = self.bot.get_channel(self.punishment_channel_id)
                if channel:
                    if unmuted_by == "System":
                        embed = self.embed_builder.build_success(
                            title='User Unmuted',
                            description=f'**User:** <@{discord_id}>\n**Reason:** `{unmute_reason}`\n**Unmuted by:** {unmuted_by} \n\nIn future if you face another punishment, it will likely increase due to your punishment history.'
                        )
                        embed.set_thumbnail(url='attachment://unbanunmute.png')
                    else:
                        embed = self.embed_builder.build_success(
                            title='User Unmuted',
                            description=f'**User:** <@{discord_id}>\n**Reason:** `{unmute_reason}`\n**Unmuted by:** <@{unmuted_by}> \n\nIn future if you face another punishment, it will likely increase due to your punishment history.'
                        )
                        embed.set_thumbnail(url='attachment://unbanunmute.png')
                    with open('asserts/punishments/unbanunmute.png', 'rb') as f:
                        file = discord.File(f, filename='unbanunmute.png')
                        await channel.send(content=f'<@{discord_id}>', file=file, embed=embed)
            return result
        except Exception as e:
            self.bot.logger.error(f"Error unmuting user {discord_id}: {e}")
            return False

    async def is_muted(self, discord_id: str) -> Optional[Dict[str, Any]]:
        try:
            current_time = Timestamp(int(datetime.now().timestamp()), 1)
            mute_data = self.db.find_one('mutes', {
                'discordid': str(discord_id),
                'unmuted': False,
                'duration': {'$gt': current_time}
            })
            if mute_data and not mute_data.get('unmuted'):
                return mute_data
            return None
        except Exception as e:
            self.bot.logger.error(f"Error checking mute status for {discord_id}: {e}")
            return None

    async def get_mute_info(self, discord_id: str) -> Optional[Dict[str, Any]]:
        try:
            mute_data = self.db.find_one('mutes', {'discordid': str(discord_id)})
            if mute_data and not mute_data.get('unmuted'):
                return mute_data
            elif mute_data and mute_data.get('unmutedate'):
                return {
                    'discordid': mute_data['discordid'],
                    'unmutereason': mute_data.get('unmutereason'),
                    'unmutedby': mute_data.get('unmutedby'),
                    'unmutedate': mute_data.get('unmutedate'),
                    'unmuted': True
                }
            return None
        except Exception as e:
            self.bot.logger.error(f"Error getting mute info for {discord_id}: {e}")
            return None
