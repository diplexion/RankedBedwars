import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.voiding import void  

class VoidCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = bot.database_manager
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='void', help='Void a game by providing the game ID.')
    async def void(self, ctx, gameid: str):
        try:
            if not ctx.guild:
                return await ctx.reply("This command can only be used in a server.")

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('void', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                return await ctx.reply(embed=embed)

            gameid = gameid.upper()
            game = self.db_manager.find_one('games', {'gameid': gameid})

            user_id = ctx.author.id
            self.db_manager.increment('users', {'discordid': str(user_id)}, {'$inc': {'voided': 1}})

            embed = self.embed_builder.build_success(
                title='Trying to void the game',
                description=f'Processing elo cal for the {gameid}. Elo changes will be reverted if the game was able to void.'
            )
            await ctx.reply(embed=embed)
            await void(self.bot, gameid, staffid=str(ctx.author.id))

        except Exception as e:
            await self.error_handler.handle_error(e, 'void game')
            embed = self.embed_builder.build_error(
                description='An error occurred while voiding the game.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(VoidCommand(bot))
