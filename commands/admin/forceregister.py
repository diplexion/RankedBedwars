import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from actions.fix import fix
from bson.timestamp import Timestamp

class ForceRegister(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()

    @commands.command(name="forceregister", help="Force register a user: !forceregister @user IGN")
    async def force_register(self, ctx: commands.Context, user: discord.User, ign: str):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission("forceregister", user_roles):
            embed = self.embed_builder.build_error(
                title="Permission Denied",
                description="You do not have permission to use this command."
            )
            await ctx.reply(embed=embed)
            return

        
        existing_ign = self.db_manager.find_one('users', {'ign': {'$regex': f'^{ign}$', '$options': 'i'}})
        if existing_ign:
            embed = self.embed_builder.build_error(
                title="IGN Taken",
                description=f"The IGN `{ign}` is already taken by another user."
            )
            await ctx.reply(embed=embed)
            return

        try:
            self.db_manager.insert('users', {
                'discordid': str(user.id),
                'ign': ign,
                'exp': 0,
                'totalexp': 0,
                'level': 1,
                'elo': 0,
                'wins': 0,
                'losses': 0,
                'kills': 0,
                'deaths': 0,
                'winstreak': 0,
                'loosestreak': 0,
                'highest_elo': 0,
                'highstwinstreak': 0,
                'bedsbroken': 0,
                'mvps': 0,
                'ss': 0,
                'scored': 0,
                'voided': 0,
                'gamesplayed': 0,
                'strikes_count': 0,
                'latest_strike_date': Timestamp(0, 1),
                'latest_strike_reason': '',
                'latest_strike_staff': '',
            })

            self.db_manager.insert('settings', {
                'discordid': str(user.id),
                'isprefixtoggled': False,
                'ispartyinvitestoggled': False,
                'isscoringpingtoggled': False,
                'staticnickname': False,
                'nickname': '',
                'theme': 'default',
                'skinpose': 'default'
            })

            await fix(self.bot, user.id, ctx.guild.id)

            embed = self.embed_builder.build_success(
                title="User Registered",
                description=f"User {user.mention} has been force registered with IGN: {ign}."
            )
            await ctx.reply(embed=embed)

            
            try:
                config = self.bot.config
                reg_log_channel_id = int(config.get('logging', {}).get('regandrename'))
                reg_log_channel = self.bot.get_channel(reg_log_channel_id)
                if reg_log_channel:
                    log_embed = discord.Embed(
                        title="Manual Force Register",
                        color=discord.Color.green()
                    )
                    log_embed.add_field(name="User", value=f"<@{user.id}> ({user.id})", inline=True)
                    log_embed.add_field(name="IGN", value=f"`{ign}`", inline=True)
                    log_embed.add_field(name="Registered By", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                    await reg_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                print(f"Failed to send regandrename log: {log_exc}")

        except Exception as e:
            embed = self.embed_builder.build_error(
                title="Registration Failed",
                description=f"Failed to register user: {e}"
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(ForceRegister(bot))
