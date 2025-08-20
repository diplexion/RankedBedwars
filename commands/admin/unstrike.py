import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager
from bson.timestamp import Timestamp

class UnstrikeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='unstrike', help='Remove a strike from a user.')
    async def unstrike(self, ctx: commands.Context, user: discord.User = None, *, reason: str = None):
        try:
            
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('unstrike', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            if not user or not reason:
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=unstrike <user> <reason>`\n\n'
                                'Example:\n`=unstrike @user Appeal accepted`'
                )
                await ctx.reply(embed=embed)
                return

            
            user_data = self.db_manager.find_one('users', {'discordid': str(user.id)})
            if not user_data:
                embed = self.embed_builder.build_error(
                    description='User not found in database. They need to be registered first.'
                )
                await ctx.reply(embed=embed)
                return

            if not user_data.get('strikes_count', 0) > 0:
                embed = self.embed_builder.build_error(
                    description='This user has no strikes to remove.'
                )
                await ctx.reply(embed=embed)
                return

            
            new_strikes = max(0, user_data.get('strikes_count', 0) - 1)
            update_data = {
                'strikes_count': new_strikes,
                'latest_strike_date': Timestamp(0, 1) if new_strikes == 0 else user_data.get('latest_strike_date', Timestamp(0, 1)),
                'latest_strike_reason': '' if new_strikes == 0 else user_data.get('latest_strike_reason', ''),
                'latest_strike_staff': '' if new_strikes == 0 else user_data.get('latest_strike_staff', '')
            }
            success = self.db_manager.update_one('users', {'discordid': str(user.id)}, {'$set': update_data})

            if success:
                
                channel = self.bot.get_channel(int(self.bot.config['channels']['punishments']))
                if channel:
                    embed = self.embed_builder.build_success(
                        title='Strikes Removed',
                        description=f'**User:** <@{user.id}> ({user_data["ign"]})\n'
                                    f'**Reason:** `{reason}`\n'
                                    f'**Staff:** <@{ctx.author.id}>'
                    )
                    embed.set_thumbnail(url='attachment://unbanunmute.png')
                    with open('asserts/punishments/unbanunmute.png', 'rb') as f:
                        file = discord.File(f, filename='unbanunmute.png')
                        await channel.send(file=file, embed=embed)

                
                embed = self.embed_builder.build_success(
                    title='Strikes Removed',
                    description=f'Successfully removed all strikes from {user.mention}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to remove strikes from user.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'unstrike user')
            try:
                embed = self.embed_builder.build_error(
                    description='An error occurred while removing strikes from the user.'
                )
                await ctx.reply(embed=embed)
            except Exception as e:
                await self.error_handler.handle_error(e, 'unstrike command response')

async def setup(bot):
    await bot.add_cog(UnstrikeCommand(bot))
