import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager

class DelQueue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.database_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='delqueue', help='Delete a queue from the database. Usage: !delqueue <channelid>')
    async def del_queue(self, ctx: commands.Context, channelid: str):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('delqueue', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            result = self.database_manager.db['queues'].delete_one({'channelid': str(channelid)})
            if result.deleted_count > 0:
                embed = self.embed_builder.build_success(
                    title='Queue Deleted',
                    description=f'Queue deleted successfully for channel ID: {channelid}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_warning(
                    description=f'No queue found for channel ID: {channelid}'
                )
                await ctx.reply(embed=embed)
        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'deleting queue')
            embed = self.embed_builder.build_error(
                description='An error occurred while deleting the queue. Please try again later.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(DelQueue(bot))
