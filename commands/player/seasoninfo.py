import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
import os

class SeasonInfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.config_path = 'configs/seasoninfo.yml'

    @commands.command(name='seasoninfo', help='View current season rules and information', alliases=['ruleset', 'rules'])
    async def seasoninfo(self, ctx: commands.Context):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('seasoninfo', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        try:
            if not os.path.exists(self.config_path):
                embed = self.embed_builder.build_error(
                    description='Season information is not available at this time.'
                )
                await ctx.reply(embed=embed, mention_author=False)
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                content = file.read()

            
            content = content.replace(':rbw_yes:', '✅')
            content = content.replace(':rbw_maybe:', '⚠️')
            content = content.replace(':rbw_no:', '❌')

            lines = content.strip().split('\n')
            title = lines[0]
            description = '\n'.join(lines[1:])

            embed = self.embed_builder.build_info(
                title=title,
                description=description
            )
            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            await self.error_handler.handle_error(e, 'seasoninfo command')
            embed = self.embed_builder.build_error(
                description='An error occurred while fetching season information. Please try again later.'
            )
            await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(SeasonInfoCommands(bot))
