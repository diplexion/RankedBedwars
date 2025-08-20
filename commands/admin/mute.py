import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager
from managers.mute_manager import MuteManager
import re

class MuteCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.mute_manager = MuteManager(bot)

    def parse_duration(self, duration_str):
        match = re.match(r"(\d+)([smhd])", duration_str)
        if not match:
            return None
        value, unit = int(match.group(1)), match.group(2)
        unit_multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        return value * unit_multipliers.get(unit, 0)

    @commands.command(name='mute', help='Mute a user from the server.\nUsage: !mute @user "reason" 1d')
    async def mute(self, ctx: commands.Context, user: discord.User, reason: str, duration: str):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('mute', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            if any(arg is None for arg in [user, reason, duration]):
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=mute <user> <reason> <duration>`\n\n'
                                'Example: `=mute @user "Toxicity" 7d`\n'
                                'Duration format: number + s/m/h/d (e.g., 1h, 2d, 30m)'
                )
                await ctx.reply(embed=embed, delete_after=15)
                return

            async with ctx.typing():
                user_data = self.db_manager.find_one('users', {'discordid': str(user.id)})
            if not user_data:
                embed = self.embed_builder.build_error(
                    description='User not found in database. They need to be registered first.'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            duration_seconds = self.parse_duration(duration)
            if duration_seconds is None:
                embed = self.embed_builder.build_error(
                    description='Invalid duration format. Please use number + s/m/h/d (e.g., 1h, 2d, 30m).'
                )
                await ctx.reply(embed=embed, delete_after=10)
                return

            success = await self.mute_manager.mute_user(
                discord_id=str(user.id),
                reason=reason,
                duration=duration,
                staffid=str(ctx.author.id)
            )

            if success:
                embed = self.embed_builder.build_success(
                    title='User Muted',
                    description=f'Successfully muted {user.mention}\n**Reason:** {reason}\n**Duration:** {duration}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to mute user. Please check the duration format and try again.'
                )
                await ctx.reply(embed=embed, delete_after=10)

        except Exception as e:
            await self.error_handler.handle_error(e, 'mute user')
            embed = self.embed_builder.build_error(
                description='An error occurred while muting the user.'
            )
            await ctx.reply(embed=embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(MuteCommand(bot))
