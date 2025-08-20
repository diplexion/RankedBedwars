import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager
from utils.error_handler import ErrorHandler

class PlayerRanksCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='ranks', help='Display available ELO ranks and their requirements')
    async def ranks_command(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('ranks', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            elo_ranks = list(self.database_manager.find('elos', {}))
            elo_ranks.sort(key=lambda x: x['minelo'])

            if not elo_ranks:
                await ctx.reply(
                    embed=self.embed_builder.build_warning(
                        title='No Ranks Available',
                        description='No ELO ranks are currently configured in the system.'
                    )
                )
                return

            ranks_description = '\n\n'.join(
                f"#{index + 1} <@&{rank['roleid']}> `{rank['minelo']} - {rank['maxelo']}` W/L: `{rank['winelo']}/{rank['loselo']}` MVP: `{rank['mvpelo']}`"
                for index, rank in enumerate(elo_ranks)
            )

            await ctx.reply(
                embed=self.embed_builder.build_success(
                    title='Available ELO Ranks',
                    description=ranks_description
                )
            )

        except Exception as e:
            await self.error_handler.handle_error(e, 'list elo ranks')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while retrieving ELO ranks.'
                )
            )

async def setup(bot):
    await bot.add_cog(PlayerRanksCommands(bot))
