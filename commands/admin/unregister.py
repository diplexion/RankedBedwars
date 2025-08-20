import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from actions.fix import fix

class Unregister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()

    @commands.command(name="unregister", help="Unregister a user by mention or ID.")
    async def unregister(self, ctx: commands.Context, user: discord.User = None):
        if user is None:
            embed = self.embed_builder.build_error(
                title="Missing Argument",
                description="Please mention a user or provide a user ID to unregister."
            )
            await ctx.reply(embed=embed)
            return

        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission("unregister", user_roles):
            embed = self.embed_builder.build_error(
                title="Permission Denied",
                description="You do not have permission to use this command."
            )
            await ctx.reply(embed=embed)
            return

        try:
            self.db_manager.delete('users', {'discordid': str(user.id)})
            embed = self.embed_builder.build_success(
                title="User Unregistered",
                description=f"User {user.mention} has been unregistered."
            )
            await ctx.reply(embed=embed)

            
            await fix(self.bot, user.id, ctx.guild.id)

        except Exception as e:
            embed = self.embed_builder.build_error(
                title="Unregistration Failed",
                description=f"Failed to unregister user: {e}"
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(Unregister(bot))
