import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager
import re

class BanCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    def parse_duration(self, duration_str):
        match = re.match(r"(\d+)([smhd])", duration_str)
        if not match:
            return None

        value, unit = int(match.group(1)), match.group(2)
        unit_multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}

        return value * unit_multipliers.get(unit, 0)

    @commands.command(name='ban', help='Ban a user from the server.\nUsage: !ban <userid> <reason> <duration>\nExample: !ban 123456789012345678 Cheating 7d')
    async def ban(self, ctx: commands.Context, user: discord.Member, reason: str = None, duration: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('ban', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if any(arg is None for arg in [user, reason, duration]):
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=ban <userid> <reason> <duration>`\n\n'
                                'Arguments:\n'
                                '• `userid`: The Discord user ID to ban\n'
                                '• `reason`: The reason for the ban\n'
                                '• `duration`: Duration format: number + s/m/h/d (e.g., 1h, 2d, 30m)\n\n'
                                'Example:\n`=ban 123456789012345678 Cheating 7d`'
                )
                await ctx.reply(embed=embed)
                return

            async with ctx.typing():
                userid = user.id
                user_data = self.db_manager.find_one('users', {'discordid': str(userid)})

            if not user_data:
                embed = self.embed_builder.build_error(
                    description='User not found in database. They need to be registered first.'
                )
                await ctx.reply(embed=embed)
                return

            duration_seconds = self.parse_duration(duration)
            if duration_seconds is None:
                embed = self.embed_builder.build_error(
                    description='Invalid duration format. Please use number + s/m/h/d (e.g., 1h, 2d, 30m).'
                )
                await ctx.reply(embed=embed)
                return

            success = await self.bot.ban_manager.ban_user(
                discord_id=str(userid),
                reason=reason,
                duration=duration,
                staffid=str(ctx.author.id)
            )

            if success:
                embed = self.embed_builder.build_success(
                    title='User Banned',
                    description=f'Successfully banned user ID `{userid}`\n'
                                f'**Reason:** {reason}\n'
                                f'**Duration:** {duration}'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to ban user. Please check the duration format and try again.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'ban user')
            try:
                embed = self.embed_builder.build_error(
                    description='An error occurred while banning the user.'
                )
                await ctx.reply(embed=embed)
            except Exception as e:
                await self.error_handler.handle_error(e, 'ban command response')

async def setup(bot):
    await bot.add_cog(BanCommand(bot))
