import discord
from discord.ext import commands

class MessageNuker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        config_channels = bot.config.get('channels', {})
        self.protected_channels = set()
        self.commands_channel = int(config_channels.get('commandschannel')) if 'commandschannel' in config_channels else None
        for name, cid in config_channels.items():
            if name != 'commandschannel':
                self.protected_channels.add(int(cid))

    @commands.Cog.listener()
    async def on_message(self, message):
        
        if message.author.bot:
            return
        
        if message.channel.id in self.protected_channels:
            try:
                await message.delete()
            except Exception:
                pass

async def setup(bot):
    await bot.add_cog(MessageNuker(bot))
