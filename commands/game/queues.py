import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager
from utils.error_handler import ErrorHandler

class PlayerQueuesCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='queues', help='Display available queues and their settings')
    async def queues_command(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('queues', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            queues = self.database_manager.find('queues', {})

            if not queues:
                await ctx.reply(
                    embed=self.embed_builder.build_warning(
                        title='No Queues Available',
                        description='No queues are currently configured in the system.'
                    )
                )
                return

            queues_description = '\n\n'.join(
                f"**Queue {index + 1}**\n"
                f"Channel: <#{queue['channelid']}>\n"
                f"Players: `{queue['maxplayers']}`\n"
                f"ELO Range: `{queue['minelo']} - {queue['maxelo']}`\n"
                f"Type: `{'Casual' if queue['iscasual'] else 'Ranked'}`"
                for index, queue in enumerate(queues)
            )

            await ctx.reply(
                embed=self.embed_builder.build_success(
                    title='Available Queues',
                    description=queues_description
                )
            )

        except Exception as e:
            await self.error_handler.handle_error(e, 'list queues')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while retrieving queues.'
                )
            )

async def setup(bot):
    await bot.add_cog(PlayerQueuesCommands(bot))
