import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class QueueCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name="queue", help="Show team details for the current game in this channel.")
    async def queue(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('queue', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            gametext_channel_id = int(self.bot.config['channels']['gametext'])
            if ctx.channel.id != gametext_channel_id:
                await ctx.reply("This command can only be used in the game text channel.")
                return

            game_channel = self.db_manager.find_one('gameschannels', {'textchannelid': str(ctx.channel.id)})
            if not game_channel:
                await ctx.reply("No game is associated with this channel.")
                return

            game_id = game_channel.get('gameid')
            game = self.db_manager.find_one('games', {'gameid': game_id})
            if not game:
                await ctx.reply("Game details could not be found.")
                return

            team1 = game.get('team1', [])
            team2 = game.get('team2', [])

            team1_details = []
            team2_details = []

            for player_id in team1:
                user = self.db_manager.find_one('users', {'discordid': str(player_id)})
                if user:
                    ign = user.get('ign', 'Unknown')
                    elo = user.get('elo', 'Unknown')
                    team1_details.append(f"- <@{player_id}> ({ign}) `elo: {elo}`")

            for player_id in team2:
                user = self.db_manager.find_one('users', {'discordid': str(player_id)})
                if user:
                    ign = user.get('ign', 'Unknown')
                    elo = user.get('elo', 'Unknown')
                    team2_details.append(f"- <@{player_id}> ({ign}) `elo: {elo}`")

            team1_mentions = '\n'.join(team1_details)
            team2_mentions = '\n'.join(team2_details)

            embed = self.bot.embed_builder.build_info(
                title=f"Teams for Game #{game_id}",
                description=(
                    f"**Team 1**\n{team1_mentions or 'No players'}\n\n"
                    f"**Team 2**\n{team2_mentions or 'No players'}"
                )
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply("An error occurred while fetching team details. Please try again later.")
            print(f"Error in queue command: {e}")

def setup(bot):
    bot.add_cog(QueueCommand(bot))
