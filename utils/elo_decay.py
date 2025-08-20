import asyncio
from datetime import datetime, timedelta

class EloDecay:
    def __init__(self, db_manager, config, bot, embed_builder):
        self.db_manager = db_manager
        self.config = config
        self.bot = bot
        self.embed_builder = embed_builder

    async def elo_decay_task(self):
        while True:
            now = datetime.now()
            if now.hour == 23 and now.minute == 15:  
                try:
                    if not self.config.get('elo_decay', {}).get('enabled', False):
                        await asyncio.sleep(60) 
                        continue

                    decay_value = self.config.get('elo_decay', {}).get('decay_value', 10)
                    decay_threshold = self.config.get('elo_decay', {}).get('decay_threshold', 1000)

                    
                    users = self.db_manager.find('users', {'elo': {'$gte': decay_threshold}})
                    for user in users:
                        if user.get('dailyelo', 0) == 0:  
                            discord_id = str(user['discordid'])  
                            new_elo = max(0, user['elo'] - decay_value)
                            self.db_manager.update_one('users', {'discordid': discord_id}, {'$set': {'elo': new_elo}})
                            print(f"Elo decayed for user {discord_id}: {user['elo']} -> {new_elo}")

                            alerts_channel_id = self.config.get('channels', {}).get('alerts')
                            if alerts_channel_id:
                                alerts_channel = self.bot.get_channel(int(alerts_channel_id))
                                if alerts_channel:
                                    embed = self.embed_builder.build_warning(
                                        title='Elo Decay Applied',
                                        description=f"User <@{discord_id}> has had their elo decayed by {decay_value}. New elo: {new_elo}"
                                    )
                                    await alerts_channel.send(embed=embed)

                    print(f"Elo decay task completed at {datetime.now()}.")
                except Exception as e:
                    print(f"Error during elo decay task: {e}")

                await asyncio.sleep(60)
            else:
                await asyncio.sleep(30)
