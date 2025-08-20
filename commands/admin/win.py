import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager

class WinCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()

    @commands.command(name='win', help='Give a win and elo change to a user by IGN.')
    async def win(self, ctx, *, ign: str):
        
        if not ctx.guild:
            return await ctx.reply("This command can only be used in a server.")

        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('win', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            return await ctx.reply(embed=embed)

        try:
            user = self.db_manager.find_one('users', {'ign': ign})
            if not user:
                embed = self.embed_builder.build_error(
                    description=f'User with IGN `{ign}` not found.'
                )
                return await ctx.reply(embed=embed)

            discordid = user['discordid']
            current_elo = user.get('elo', 0)
            wins = user.get('wins', 0)
            winstreak = user.get('winstreak', 0)
            highstwinstreak = user.get('highstwinstreak', 0)
            daily_elo = user.get('dailyelo', 0)

            
            rank = self.db_manager.find_one('elos', {
                'minelo': {'$lte': current_elo},
                'maxelo': {'$gte': current_elo}
            })

            if not rank:
                embed = self.embed_builder.build_error(
                    description=f'Rank not found for elo {current_elo}.'
                )
                return await ctx.reply(embed=embed)

            win_elo = rank.get('winelo', 0)
            new_elo = max(0, current_elo + win_elo)
            wins += 1
            winstreak += 1
            highstwinstreak = max(highstwinstreak, winstreak)
            daily_elo += win_elo

            self.db_manager.update_one('users', {'discordid': discordid}, {'$set': {
                'elo': new_elo,
                'wins': wins,
                'winstreak': winstreak,
                'highstwinstreak': highstwinstreak,
                'dailyelo': daily_elo
            }})

            embed = self.embed_builder.build_success(
                title='Win Given',
                description=f'Gave a win and +{win_elo} elo to `{ign}`. New elo: {new_elo}'
            )
            await ctx.reply(embed=embed)

            
            try:
                config = self.bot.config
                mod_log_channel_id = int(config.get('logging', {}).get('modification'))
                mod_log_channel = self.bot.get_channel(mod_log_channel_id)
                if mod_log_channel:
                    log_embed = discord.Embed(
                        title="Manual Win Given",
                        color=discord.Color.blurple()
                    )
                    log_embed.add_field(name="User", value=f"<@{discordid}> ({discordid})", inline=True)
                    log_embed.add_field(name="IGN", value=f"`{ign}`", inline=True)
                    log_embed.add_field(name="Old ELO", value=f"{current_elo}", inline=True)
                    log_embed.add_field(name="New ELO", value=f"{new_elo}", inline=True)
                    log_embed.add_field(name="Given By", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                    log_embed.add_field(name="Win ELO", value=f"+{win_elo}", inline=True)
                    await mod_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                await self.error_handler.handle_error(log_exc, 'win command logging')

        except Exception as e:
            await self.error_handler.handle_error(e, 'win command')
            embed = self.embed_builder.build_error(
                description='An error occurred while giving a win.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(WinCommand(bot))
