import os
import discord

class EventManager:
    def __init__(self, bot):
        self.bot = bot
        
    async def setup_events(self) -> None:
        events_folder = 'events'
        
        loaded_extensions = set()
        
        for filename in os.listdir(events_folder):
            if filename.endswith('.py') and not filename.startswith('__'):
                cog_name = f"{events_folder}.{filename[:-3]}"
                
                
                if cog_name in loaded_extensions or cog_name in self.bot.extensions:
                    continue
                    
                try:
                    await self.bot.load_extension(cog_name)
                    loaded_extensions.add(cog_name)
                except Exception as e:
                    self.bot.logger.error(f"Failed to load event cog {cog_name}: {e}")
