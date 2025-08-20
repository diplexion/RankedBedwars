import yaml
import os
import discord
from datetime import datetime
from managers.database_manager import DatabaseManager
from managers.ban_manager import BanManager
import asyncio
from bson.timestamp import Timestamp

class StrikesManager:
    def __init__(self, bot, config_path: str = 'configs/config.yml'):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.ban_manager = BanManager(bot)
        self.strikes_config = self.load_strikes_config(config_path)
        self.auto_remove_task = None
        self.embed_builder = bot.embed_builder
        self.punishment_channel_id = int(bot.config['channels']['punishments'])

    def load_strikes_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config.get('strikes', {})
        except Exception as e:
            print(f"Failed to load strikes configuration: {e}")
            raise

    def get_strike_action(self, strike_count: int) -> str:
        return self.strikes_config.get(f'{strike_count}strike', 'No action')

    async def apply_strike(self, discord_id: str, staff_id: str, ign: str, reason: str) -> bool:
        return await self.add_strike(discord_id, reason, staff_id)

    async def add_strike(self, discord_id: str, reason: str, staff_id: str) -> bool:
        try:
            
            user_data = self.db_manager.find_one('users', {'discordid': str(discord_id)})
            if not user_data:
                raise ValueError(f"User with Discord ID {discord_id} not found in database")

            current_strikes = user_data.get('strikes_count', 0)
            new_strike_count = current_strikes + 1

            
            strike_actions = self.bot.config['strikes']
            strike_keys = sorted([int(k.replace('strike', '')) for k in strike_actions.keys()])
            
            
            action = None
            for strike_num in strike_keys:
                if new_strike_count <= strike_num:
                    action = strike_actions[f'{strike_num}strike']
                    break
            
            
            if action is None and strike_keys:
                last_strike = max(strike_keys)
                action = strike_actions[f'{last_strike}strike']

            
            formatted_reason = f"[Strike System] {reason}"

            
            update_data = {
                'strikes_count': new_strike_count,
                'latest_strike_date': Timestamp(int(datetime.now().timestamp()), 1),
                'latest_strike_reason': formatted_reason,
                'latest_strike_staff': str(staff_id)
            }
            self.db_manager.update_one('users', {'discordid': str(discord_id)}, {'$set': update_data})

            
            strike_data = {
                'discordid': str(discord_id),
                'staffid': str(staff_id),
                'ign': user_data['ign'],
                'reason': formatted_reason,
                'date': Timestamp(int(datetime.now().timestamp()), 1)
            }
            self.db_manager.insert('strikes', strike_data)

            
            if action and action != 'warn':
                
                await self.ban_manager.ban_user(discord_id, formatted_reason, action, staff_id)

            
            channel = self.bot.get_channel(self.punishment_channel_id)
            if channel:
                embed = self.embed_builder.build_warning(
                    title='Strike Issued',
                    description=f'**User:** <@{discord_id}>\n**Reason:** `{formatted_reason}`\n**Strike Count:** `{new_strike_count}`\n**Action:** `{action}`\n**Staff:** <@{staff_id}>'
                )
                embed.set_thumbnail(url='attachment://strike.png')
                with open('asserts/punishments/strike.png', 'rb') as f:
                    file = discord.File(f, filename='strike.png')
                    await channel.send(content=f'<@{discord_id}>', file=file, embed=embed)

            return True
        except Exception as e:
            self.bot.logger.error(f"Error adding strike for user {discord_id}: {e}")
            return False

    async def start_auto_remove_strikes(self):
        if self.auto_remove_task is None:
            self.auto_remove_task = asyncio.create_task(self._auto_remove_strikes_loop())

    async def start_strikes_checker(self):
        await self.start_auto_remove_strikes()

    async def stop_auto_remove_strikes(self):
        if self.auto_remove_task:
            self.auto_remove_task.cancel()
            self.auto_remove_task = None

    async def _auto_remove_strikes_loop(self):
        while True:
            try:
                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                thirty_days_ago = Timestamp(int(datetime.now().timestamp() - (30 * 24 * 60 * 60)), 1)

                
                users_to_update = self.db_manager.find('users', {
                    'strikes_count': {'$gt': 0},
                    'latest_strike_date': {'$lt': thirty_days_ago}
                })

                for user in users_to_update:
                    
                    update_data = {
                        'strikes_count': 0,
                        'latest_strike_date': None,
                        'latest_strike_reason': None,
                        'latest_strike_staff': None
                    }
                    self.db_manager.update_one('users', {'discordid': user['discordid']}, {'$set': update_data})
                    print(f"Removed strikes for user {user['discordid']}")

                    
                    self.db_manager.update_one(
                        'strikes',
                        {'discordid': str(user['discordid']), 'reason': user['latest_strike_reason']},
                        {
                            '$set': {
                                'removed': True,
                                'removed_reason': 'Strike expired after 30 days',
                                'removed_by': 'System',
                                'removed_date': Timestamp(int(datetime.now().timestamp()), 1)
                            }
                        }
                    )

                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error in auto remove strikes loop: {e}")
                await asyncio.sleep(1)

    def close(self):
        self.db_manager.close()
        self.stop_auto_remove_strikes()
