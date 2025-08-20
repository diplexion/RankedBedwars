import discord
from discord.ext import commands
from actions.fix import fix
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class PlayerFixCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='fix', help='Fix roles and nickname for yourself or another user.', aliases=['update'])
    async def fix_command(self, ctx, member: discord.Member = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('fix', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            target_user = member if member else ctx.author

            await fix(self.bot, target_user.id, str(ctx.guild.id))

            if member:
                description = f'Roles and nickname have been updated for {target_user.mention}!'
            else:
                description = f'{ctx.author.mention}, your roles and nickname have been updated!'

            embed = self.embed_builder.build_success(
                title='Fix Successful',
                description=description
            )
            await ctx.reply(embed=embed)
            print(f"Called fix function for user {target_user.id}")

        except discord.errors.Forbidden:
            embed = self.embed_builder.build_error(
                description="The bot doesn't have permissions to update the user's info."
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            await self.error_handler.handle_error(e, 'player fix')
            embed = self.embed_builder.build_error(
                description='An error occurred while fixing roles and nickname. Please try again later.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(PlayerFixCommands(bot))
