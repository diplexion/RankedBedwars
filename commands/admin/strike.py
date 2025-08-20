import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager

class StrikeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='strike', help='Give a strike to a user.\nUsage: !strike @user <reason>')
    async def strike(self, ctx, member: discord.Member = None, *, reason: str = None):
        try:
            
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('strike', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            if not member or not reason:
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=strike @user <reason>`\n\nExample:\n`=strike @user Inappropriate behavior`'
                )
                await ctx.reply(embed=embed)
                return

            
            async with ctx.typing():
                user_data = self.db_manager.find_one('users', {'discordid': str(member.id)})
                
            if not user_data:
                embed = self.embed_builder.build_error(
                    description='User not found in database. They need to be registered first.'
                )
                await ctx.reply(embed=embed)
                return

            
            success = await self.bot.strikes_manager.apply_strike(
                discord_id=str(member.id),
                staff_id=str(ctx.author.id),
                ign=user_data['ign'],
                reason=reason
            )

            if success:
                embed = self.embed_builder.build_success(
                    title='Strike Added',
                    description=f'Successfully gave a strike to {member.mention}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to add strike to user.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'strike command')
            error_embed = self.embed_builder.build_error(
                description='An error occurred while striking the user.'
            )
            await ctx.reply(embed=error_embed)

def setup(bot):
    bot.add_cog(StrikeCommand(bot))
