import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class UnbanCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='unban', help='Unban a user from the server.\nUsage: !unban <user_id> <reason>')
    async def unban(self, ctx, user_id: int = None, *, reason: str = None):
        try:
            
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('unban', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            if not user_id or not reason:
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=unban <user_id> <reason>`\n\nExample:\n`=unban 123456789012345678 Appeal accepted`'
                )
                await ctx.reply(embed=embed)
                return

            
            ban_info = await self.bot.ban_manager.get_ban_info(user_id)
            if not ban_info or ban_info.get('unbanned', False):
                embed = self.embed_builder.build_error(
                    description=f'User with ID `{user_id}` is not currently banned.'
                )
                await ctx.reply(embed=embed)
                return

            
            success = await self.bot.ban_manager.unban_user(
                discord_id=str(user_id),
                unban_reason=reason,
                unbanned_by=str(ctx.author.id)
            )

            if success:
                try:
                    user_obj = await self.bot.fetch_user(user_id)
                    user_mention = user_obj.mention
                except:
                    user_mention = f"`{user_id}`"

                embed = self.embed_builder.build_success(
                    title='User Unbanned',
                    description=f'Successfully unbanned {user_mention}\n**Reason:** {reason}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to unban user. Please try again.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'unban command')
            embed = self.embed_builder.build_error(
                description='An error occurred while unbanning the user.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(UnbanCommand(bot))
