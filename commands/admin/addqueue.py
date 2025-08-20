import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager
from utils.error_handler import ErrorHandler

class AddQueue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.database_manager = DatabaseManager()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()  

    @commands.command(name='addqueue', help='Add a new queue to the database.')
    async def add_queue(
        self, ctx, 
        channelid: str, 
        maxplayers: int, 
        minelo: int, 
        maxelo: int, 
        iscasual: bool
    ):
        try:
            channelid = int(channelid)
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('addqueue', user_roles, user_id=ctx.author.id):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if maxplayers < 2:
                embed = self.embed_builder.build_error(
                    description='Maximum players must be at least 2.'
                )
                await ctx.reply(embed=embed)
                return

            if minelo >= maxelo:
                embed = self.embed_builder.build_error(
                    description='Minimum ELO must be less than maximum ELO.'
                )
                await ctx.reply(embed=embed)
                return

            existing_queue = self.database_manager.find_one('queues', {'channelid': str(channelid)})
            if existing_queue:
                embed = self.embed_builder.build_error(
                    description=f'A queue for channel {channelid} already exists.'
                )
                await ctx.reply(embed=embed)
                return

            document = {
                'channelid': str(channelid),
                'maxplayers': maxplayers,
                'minelo': minelo,
                'maxelo': maxelo,
                'iscasual': iscasual
            }

            self.database_manager.insert('queues', document)

            embed = self.embed_builder.build_success(
                title='Queue Added',
                description=f'Successfully added queue for channel {channelid}\n'
                            f'Maximum Players: `{maxplayers}`\n'
                            f'ELO Range: `{minelo} - {maxelo}`\n'
                            f'Casual Queue: `{"Yes" if iscasual else "No"}`'
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'add queue configuration')
            embed = self.embed_builder.build_error(
                description='An error occurred while adding the queue configuration.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(AddQueue(bot))
