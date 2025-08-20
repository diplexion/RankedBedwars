import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager
from managers.mute_manager import MuteManager
import yaml
import os

class UnmuteCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.mute_manager = MuteManager(bot)
        self.config = self.load_config()

    def load_config(self):
        config_path = os.path.join('configs', 'config.yml')
        with open(config_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    @commands.command(name='unmute', help='Unmute a user in the server.\nUsage: !unmute <user_mention_or_id> [reason]')
    async def unmute(self, ctx, user: discord.User = None, *, reason: str = "No reason provided"):
        try:
            
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('unmute', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            if not user:
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=unmute <user> [reason]`\n\nExample:\n`=unmute @user Spoke with them.`'
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

            
            success = await self.mute_manager.unmute_user(
                discord_id=str(user.id),
                unmute_reason=reason,
                unmuted_by=str(ctx.author.id)
            )

            if success:
                embed = self.embed_builder.build_success(
                    title='User Unmuted',
                    description=f'Successfully unmuted {user.mention}\n**Reason:** {reason}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to unmute user. Please try again.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'unmute user')
            embed = self.embed_builder.build_error(
                description='An error occurred while unmuting the user.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(UnmuteCommand(bot))
