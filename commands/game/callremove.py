import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class CallRemoveCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='callremove', help='Remove a user from a game voice channel.')
    async def callremove(self, ctx, targetuser: discord.User):
        try:
            if not isinstance(ctx.author, discord.Member):
                return  

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('callremove', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if not ctx.author.voice or not ctx.author.voice.channel:
                embed = self.bot.embed_builder.build_error(
                    description='You must be in a voice channel to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            user_voice_channel = ctx.author.voice.channel
            games_channel = self.db_manager.find_one('gameschannels', {'$or': [
                {'team1voicechannelid': user_voice_channel.id},
                {'team2voicechannelid': user_voice_channel.id},
                {'pickingvoicechannelid': user_voice_channel.id}
            ]})

            if not games_channel:
                embed = self.bot.embed_builder.build_error(
                    description='Your current voice channel is not associated with any game.'
                )
                await ctx.reply(embed=embed)
                return

            game_id = games_channel['gameid']
            target_in_game = self.db_manager.find_one('games', {'gameid': game_id, '$or': [
                {'team1': str(targetuser.id)},
                {'team2': str(targetuser.id)}
            ]})

            if target_in_game:
                embed = self.bot.embed_builder.build_error(
                    description=f'{targetuser.name} is already part of the game and cannot be removed.'
                )
                await ctx.reply(embed=embed)
                return

            await user_voice_channel.set_permissions(targetuser, overwrite=None)
            embed = self.bot.embed_builder.build_success(
                description=f'{targetuser.name} has been removed from the voice channel.'
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'callremove command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while processing your request. Please try again later.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(CallRemoveCommands(bot))
