import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager

class WipeCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='wipe', help='Reset all stats for a specific player by IGN')
    async def wipe(self, ctx, *, ign: str):
        try:
            if not ctx.guild:
                return await ctx.reply("This command must be used in a server.")

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('wipe', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                return await ctx.reply(embed=embed)

            
            user = self.db_manager.find_one('users', {'ign': ign})
            if not user:
                embed = self.embed_builder.build_error(
                    description=f'User with IGN "{ign}" not found.'
                )
                return await ctx.reply(embed=embed)

            
            reset_stats = {
                'elo': 0,
                'dailyelo': 0,
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
                'gamesplayed': 0
            }

            
            success = self.db_manager.update_one(
                'users',
                {'ign': ign},
                {'$set': reset_stats}
            )

            
            self.db_manager.db['recentgames'].delete_many({'discordid': user['discordid']})

            if success:
                embed = self.embed_builder.build_success(
                    title='Stats Wiped',
                    description=f'Successfully reset all stats for player **{ign}**'
                )
                await ctx.reply(embed=embed)

                
                try:
                    config = self.bot.config if hasattr(self.bot, 'config') else None
                    if not config:
                        import yaml, os
                        config_path = os.path.join('configs', 'config.yml')
                        with open(config_path, 'r', encoding='utf-8') as file:
                            config = yaml.safe_load(file)
                    mod_log_channel_id = int(config.get('logging', {}).get('modification'))
                    mod_log_channel = self.bot.get_channel(mod_log_channel_id)
                    if mod_log_channel:
                        log_embed = discord.Embed(
                            title='Player Stats Wiped',
                            color=discord.Color.red()
                        )
                        log_embed.add_field(name='Player', value=f"{ign} ({user['discordid']})", inline=True)
                        log_embed.add_field(name='Wiped By', value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                        log_embed.add_field(name='Time', value=f"<t:{int(ctx.message.created_at.timestamp())}:F>", inline=True)
                        log_embed.set_footer(text=f"Guild ID: {ctx.guild.id}")
                        await mod_log_channel.send(embed=log_embed)
                except Exception as log_exc:
                    print(f"Failed to send modification log: {log_exc}")

                
                channel = self.bot.get_channel(int(self.bot.config['channels']['punishments']))
                if channel:
                    log_embed2 = self.embed_builder.build_warning(
                        title='Stats Wiped',
                        description=f'**Player:** {ign}\n'
                                    f'**Wiped by:** {ctx.author.mention}\n'
                                    f'**Time:** <t:{int(ctx.message.created_at.timestamp())}:F>'
                    )
                    await channel.send(embed=log_embed2)
            else:
                embed = self.embed_builder.build_error(
                    description=f'Failed to reset stats for player **{ign}**'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'wipe command')
            embed = self.embed_builder.build_error(
                description='An unexpected error occurred while wiping stats.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(WipeCommand(bot))
