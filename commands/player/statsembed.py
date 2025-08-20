import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager

class PlayerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()

    @commands.command(name='statsembed', help='View player statistics')
    async def statsembed(self, ctx: commands.Context, *, identifier: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('statsembed', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    ),
                    mention_author=False
                )
                return

            
            user_id = None
            if identifier:
                if identifier.startswith('<@') and identifier.endswith('>'):
                    user_id = identifier.strip('<@!>')
                elif identifier.isdigit():
                    user_id = identifier
                else:
                    query = {'ign': {'$regex': f'^{identifier}$', '$options': 'i'}}
                    player = self.database_manager.find_one('users', query)
                    if not player:
                        await ctx.reply(
                            embed=self.embed_builder.build_error(
                                title='Player Not Found',
                                description=f'No stats found for IGN: {identifier}'
                            ),
                            mention_author=False
                        )
                        return
                    user_id = player['discordid']
            else:
                user_id = str(ctx.author.id)

            player = self.database_manager.find_one('users', {'discordid': user_id})
            if not player:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Player Not Found',
                        description='No stats found for the specified user.'
                    ),
                    mention_author=False
                )
                return

            try:
                recent_games = list(self.database_manager.db['recentgames'].find({'discordid': user_id}))
                recent_games.sort(key=lambda x: int(x.get('id', '0')), reverse=True)
                recent_games = recent_games[:5]
            except Exception as e:
                print(f"Error sorting recent games: {e}")
                recent_games = list(self.database_manager.db['recentgames'].find(
                    {'discordid': user_id}
                ).sort([('id', -1)]).limit(5))

            recent_games_list = []
            for game in recent_games:
                emoji = '🏆' if game.get('ismvp', False) else {
                    'win': '🟢',
                    'lose': '🔴',
                    'voided': '⚫',
                    'pending': '🟡',
                    'submitted': '⏳'
                }.get(game.get('result'), '❓')
                recent_games_list.append(f" - Game #{game.get('gameid', 'N/A')} {emoji}")

            recent_games_str = '\n'.join(recent_games_list) if recent_games_list else 'None played yet'
            daily_elo = player.get('dailyelo', 0)

            stats_description = (
                f"Level: {player.get('level', 'None')}\n"
                f"Experience: {player.get('exp', 'None')}\n"
                f"Total Experience: {player.get('totalexp', 'None')}\n"
                f"Elo: {player['elo']}\n"
                f"Daily Elo: {daily_elo}\n"
                f"Wins: {player['wins']}\n"
                f"Losses: {player['losses']}\n"
                f"Kills: {player['kills']}\n"
                f"Deaths: {player['deaths']}\n"
                f"Win Streak: {player['winstreak']}\n"
                f"Lose Streak: {player['loosestreak']}\n"
                f"Highest Elo: {player['highest_elo']}\n"
                f"Highest Win Streak: {player['highstwinstreak']}\n"
                f"Beds Broken: {player['bedsbroken']}\n"
                f"MVPs: {player['mvps']}\n"
                f"Recent Games:\n{recent_games_str}"
            )

            await ctx.reply(
                embed=self.embed_builder.build_success(
                    title=f"Stats for {player['ign']}",
                    description=stats_description
                ),
                mention_author=False
            )

        except Exception as e:
            await self.error_handler.handle_error(e, 'statsembed command')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while fetching stats. Please try again later.'
                ),
                mention_author=False
            )

async def setup(bot):
    await bot.add_cog(PlayerStats(bot))
