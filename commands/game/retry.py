import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class RetryGameCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name="retry", help="Retry the current game")
    async def retry_game(self, ctx: commands.Context):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('retry', user_roles):
            embed = discord.Embed(
                title='Permission Denied',
                description='You do not have permission to use this command.',
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        try:
            
            channel_id = str(ctx.channel.id)
            
            
            game_channel = self.db_manager.find_one("gameschannels", {"textchannelid": channel_id})
            if not game_channel:
                embed = discord.Embed(
                    title="Error",
                    description="This command can only be used in a game channel.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return
                
            game_id = game_channel.get("gameid")
            if not game_id:
                embed = discord.Embed(
                    title="Error",
                    description="Could not find game ID for this channel.",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return
            
            
            game = self.db_manager.find_one("games", {"gameid": game_id})
            if not game:
                embed = discord.Embed(
                    title="Error",
                    description=f"Could not find game data for game ID: {game_id}",
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

            
            self.db_manager.update_one("games", {"gameid": game_id}, {"$set": {"retry_attempted": True}})

            embed = discord.Embed(
                title="Game Retry Marked",
                description=f"Game {game_id} has been marked for retry. Since external API is disabled, this is a database-only operation.",
                color=discord.Color.green()
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"An error occurred while retrying the game: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(RetryGameCommand(bot))
