import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.fix import fix

EDITABLE_FIELDS = [
    'level', 'elo', 'dailyelo', 'wins', 'losses', 'kills', 'deaths', 'winstreak',
    'loosestreak', 'highest_elo', 'highstwinstreak', 'bedsbroken', 'mvps', 'ss',
    'scored', 'voided', 'gamesplayed'
]

class EditUserCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        from managers.permission_manager import PermissionManager
        self.permission_manager = PermissionManager()

    @commands.command(name='edit', help='Edit a user stat. Usage: !edit <ign> <field> <value>')
    async def edit(self, ctx: commands.Context, ign: str, field: str, value: str):
        
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('edit', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        if field not in EDITABLE_FIELDS:
            embed = self.embed_builder.build_error(
                description=f'Invalid field `{field}`. Valid fields: {", ".join(EDITABLE_FIELDS)}'
            )
            await ctx.reply(embed=embed)
            return

        try:
            user = self.db_manager.find_one('users', {'ign': ign})
            if not user:
                embed = self.embed_builder.build_error(description=f'User with IGN `{ign}` not found.')
                await ctx.reply(embed=embed)
                return

            try:
                delta = int(value)
            except Exception:
                embed = self.embed_builder.build_error(description='Value must be an integer (can be negative or positive).')
                await ctx.reply(embed=embed)
                return

            current_val = int(user.get(field, 0))
            new_val = current_val + delta
            if new_val < 0:
                new_val = 0

            self.db_manager.update_one('users', {'ign': ign}, {'$set': {field: new_val}})

            
            await fix(self.bot, user['discordid'], ctx.guild.id)

            embed = self.embed_builder.build_success(
                title='User Updated',
                description=f'Updated `{field}` for `{ign}` from `{current_val}` to `{new_val}`.'
            )
            await ctx.reply(embed=embed)

            
            try:
                config = self.bot.config
                mod_log_channel_id = int(config.get('logging', {}).get('modification'))
                mod_log_channel = self.bot.get_channel(mod_log_channel_id)
                if mod_log_channel:
                    log_embed = discord.Embed(
                        title="Manual User Edit",
                        color=discord.Color.gold()
                    )
                    log_embed.add_field(name="User", value=f"<@{user['discordid']}> ({user['discordid']})", inline=True)
                    log_embed.add_field(name="IGN", value=f"`{ign}`", inline=True)
                    log_embed.add_field(name="Field", value=f"{field}", inline=True)
                    log_embed.add_field(name="Old Value", value=f"{current_val}", inline=True)
                    log_embed.add_field(name="New Value", value=f"{new_val}", inline=True)
                    log_embed.add_field(name="Edited By", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                    await mod_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                await self.error_handler.handle_error(log_exc, 'edit command logging')

        except Exception as e:
            await self.error_handler.handle_error(e, 'edit user')
            embed = self.embed_builder.build_error(description='An error occurred while editing the user.')
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(EditUserCommand(bot))
