import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from actions.voiding import void

class ForceVoidCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.db_manager = DatabaseManager()

    @commands.command(name='forcevoid', help='Force void the current game.')
    async def forcevoid(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('forcevoid', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            channel_data = self.db_manager.find_one('gameschannels', {'textchannelid': str(ctx.channel.id)})
            if not channel_data:
                embed = self.bot.embed_builder.build_error(
                    description='This command can only be used in a game channel.'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            game_id = channel_data.get('gameid')
            game = self.db_manager.find_one('games', {'gameid': game_id})
            if not game:
                embed = self.bot.embed_builder.build_error(
                    description=f'Game with ID {game_id} not found.'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            embed = self.bot.embed_builder.build_success(
                title='Game Voided',
                description=f'Game {game_id} has been successfully voided.'
            )
            await ctx.reply(embed=embed)
            await void(self.bot, game_id, str(ctx.author.id))

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'force void command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while voiding the game. Please try again later.'
            )
            await ctx.reply(embed=embed, delete_after=10)

def setup(bot):
    bot.add_cog(ForceVoidCommand(bot))
