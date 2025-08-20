import discord
from discord.ext import commands

class VoiceChannelNuker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.gameschannels = set()
        self._refresh_gameschannels()

    def _refresh_gameschannels(self):
        try:
            db = self.bot.database_manager.db
            channels = db['gameschannels'].find({}, {'_id': 0, 'textchannelid': 1, 'team1voicechannelid': 1, 'team2voicechannelid': 1, 'pickingvoicechannelid': 1})
            self.gameschannels.clear()
            for ch in channels:
                for key in ['textchannelid', 'team1voicechannelid', 'team2voicechannelid', 'pickingvoicechannelid']:
                    cid = ch.get(key)
                    if cid:
                        try:
                            self.gameschannels.add(int(cid))
                        except Exception as e:
                            self.bot.logger.error(f"Could not convert channel id {cid} to int: {e}")
        except Exception as e:
            self.bot.logger.error(f"Failed to fetch gameschannels: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        self._refresh_gameschannels()
        if before.channel and (not after.channel or before.channel.id != after.channel.id):
            channel = before.channel
            if channel.id in self.gameschannels:
                if len(channel.members) == 0:
                    db = self.bot.database_manager.db
                    gameschannel_entry = db['gameschannels'].find_one({
                        '$or': [
                            {'textchannelid': str(channel.id)},
                            {'team1voicechannelid': str(channel.id)},
                            {'team2voicechannelid': str(channel.id)},
                            {'pickingvoicechannelid': str(channel.id)}
                        ]
                    })
                    if gameschannel_entry and 'gameid' in gameschannel_entry:
                        gameid = gameschannel_entry['gameid']
                        game = db['games'].find_one({'gameid': gameid})
                        if game and (game.get('state') == 'scored' or game.get('state') == 'voided'):
                            try:
                                await channel.delete(reason="Game ended and all users left.")
                            except Exception as e:
                                self.bot.logger.error(f"Failed to delete voice channel {channel.id}: {e}")

    
    @commands.command(hidden=True)
    async def refreshgameschannels(self, ctx):
        self._refresh_gameschannels()
        await ctx.send("Games channels cache refreshed.")

async def setup(bot):
    await bot.add_cog(VoiceChannelNuker(bot))
