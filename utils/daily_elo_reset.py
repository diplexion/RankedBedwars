import asyncio
from datetime import datetime, timedelta

class DailyEloReset:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def reset_daily_elo_task(self):
        while True:
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                try:
                    self.db_manager.reset_daily_elo()
                    print(f"Daily elo reset completed at {datetime.now()}.")
                except Exception as e:
                    print(f"Error during daily elo reset: {e}")

                
                await asyncio.sleep(60)
            else:
                
                await asyncio.sleep(30)
