import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class DelEloCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='delelo', help='Delete an existing ELO role configuration. Usage: !delelo <roleid>')
    async def delelo(self, ctx, roleid: str):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('delelo', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            existing_role = self.bot.database_manager.find_one('elos', {'roleid': str(roleid)})
            if not existing_role:
                embed = self.embed_builder.build_error(
                    description=f'No ELO configuration found for role {roleid}.'
                )
                await ctx.reply(embed=embed)
                return

            self.bot.database_manager.delete('elos', {'roleid': str(roleid)})

            embed = self.embed_builder.build_success(
                title='ELO Configuration Deleted',
                description=f'Successfully deleted ELO configuration for role {roleid}.'
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'delete elo configuration')
            embed = self.embed_builder.build_error(
                description='An error occurred while deleting ELO configuration.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(DelEloCommand(bot))
