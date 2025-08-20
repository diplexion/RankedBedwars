import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class CallCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='call', help='Call a user to your current game voice channel.')
    async def call(self, ctx, target: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_permission('call', user_roles):
            embed = self.bot.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            
            if not ctx.author.voice or not ctx.author.voice.channel:
                embed = self.bot.embed_builder.build_error(
                    description='You must be in a voice channel to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            voice_channel_id = ctx.author.voice.channel.id

            
            games_channel = self.db_manager.find_one('gameschannels', {
                '$or': [
                    {'team1voicechannelid': voice_channel_id},
                    {'team2voicechannelid': voice_channel_id},
                    {'pickingvoicechannelid': voice_channel_id}
                ]
            })

            if not games_channel:
                embed = self.bot.embed_builder.build_error(
                    description='Your current voice channel is not associated with any game.'
                )
                await ctx.reply(embed=embed)
                return

            
            recent_games = self.db_manager.find('recentgames', {
                'discordid': str(ctx.author.id),
                'gameid': games_channel['gameid'],
                'state': 'pending'
            })

            if not recent_games:
                embed = self.bot.embed_builder.build_error(
                    description='No pending games found for you in this voice channel.'
                )
                await ctx.reply(embed=embed)
                return


            
            try:
                role = discord.utils.get(ctx.guild.roles, id=games_channel['roleid'])
                if role:
                    await target.add_roles(role)
                channel = ctx.guild.get_channel(voice_channel_id)
                if channel:
                    await channel.set_permissions(target, connect=True, speak=True)
                else:
                    embed = self.bot.embed_builder.build_error(
                        description='Voice channel not found or already deleted.'
                    )
                    await ctx.reply(embed=embed)
                    return
            except discord.NotFound:
                embed = self.bot.embed_builder.build_error(
                    description='Could not grant permissions because the channel or user was not found.'
                )
                await ctx.reply(embed=embed)
                return
            except Exception as e:
                await self.bot.error_handler.handle_error(e, 'call command (permission grant)')
                embed = self.bot.embed_builder.build_error(
                    description='An error occurred while granting permissions.'
                )
                await ctx.reply(embed=embed)
                return

            embed = self.bot.embed_builder.build_success(
                description=f'{target.mention} has been granted access to the voice channel for your game.'
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'call command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while processing your request. Please try again later.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(CallCommands(bot))
