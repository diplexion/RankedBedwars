import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager

class LooseCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='loose', help='Give a loss and ELO change to a user by IGN.')
    async def loose(self, ctx: commands.Context, ign: str):
        permission_manager = PermissionManager()
        user_roles = [role.id for role in ctx.author.roles]

        if not permission_manager.has_permission('loose', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed, delete_after=10)
            return

        try:
            user = self.db_manager.find_one('users', {'ign': ign})
            if not user:
                embed = self.embed_builder.build_error(description=f'User with IGN `{ign}` not found.')
                await ctx.reply(embed=embed, delete_after=10)
                return

            discordid = user['discordid']
            current_elo = user.get('elo', 0)
            losses = user.get('losses', 0)
            loosestreak = user.get('loosestreak', 0)
            winstreak = user.get('winstreak', 0)
            daily_elo = user.get('dailyelo', 0)

            rank = self.db_manager.find_one('elos', {
                'minelo': {'$lte': current_elo},
                'maxelo': {'$gte': current_elo}
            })
            if not rank:
                embed = self.embed_builder.build_error(description=f'Rank not found for ELO {current_elo}.')
                await ctx.reply(embed=embed, delete_after=10)
                return

            lose_elo = rank.get('loselo', 0)
            new_elo = max(0, current_elo - lose_elo)
            losses += 1
            loosestreak += 1
            winstreak = 0
            daily_elo = max(0, daily_elo - lose_elo)

            self.db_manager.update_one('users', {'discordid': discordid}, {'$set': {
                'elo': new_elo,
                'losses': losses,
                'loosestreak': loosestreak,
                'winstreak': winstreak,
                'dailyelo': daily_elo
            }})

            embed = self.embed_builder.build_success(
                title='Loss Given',
                description=f'Gave a loss and -{lose_elo} ELO to `{ign}`. New ELO: {new_elo}'
            )
            await ctx.reply(embed=embed)

            
            try:
                config = self.bot.config
                mod_log_channel_id = int(config.get('logging', {}).get('modification'))
                mod_log_channel = self.bot.get_channel(mod_log_channel_id)
                if mod_log_channel:
                    log_embed = discord.Embed(
                        title="Manual Loss Given",
                        color=discord.Color.red()
                    )
                    log_embed.add_field(name="User", value=f"<@{discordid}> ({discordid})", inline=True)
                    log_embed.add_field(name="IGN", value=f"`{ign}`", inline=True)
                    log_embed.add_field(name="Old ELO", value=f"{current_elo}", inline=True)
                    log_embed.add_field(name="New ELO", value=f"{new_elo}", inline=True)
                    log_embed.add_field(name="Given By", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                    log_embed.add_field(name="Loss ELO", value=f"-{lose_elo}", inline=True)
                    await mod_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                await self.error_handler.handle_error(log_exc, 'loose command logging')

        except Exception as e:
            await self.error_handler.handle_error(e, 'loose command')
            embed = self.embed_builder.build_error(description='An error occurred while giving a loss.')
            await ctx.reply(embed=embed, delete_after=10)

async def setup(bot):
    await bot.add_cog(LooseCommand(bot))
