import discord
from discord.ext import commands
from actions.fix import fix
import asyncio
import time
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class FixAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.max_workers = 3
        self.rate_limit_hits = 0

    @commands.command(name='fixall', help='Fix all users in the server (developer only)')
    async def fixall(self, ctx):
        try:
            if not ctx.guild:
                return await ctx.reply("This command must be used in a server.")

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('developer', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                return await ctx.reply(embed=embed)

            guild = ctx.guild
            members = guild.members
            total_members = len(members)
            progress_message = await ctx.reply(
                embed=self.embed_builder.build_info(
                    title="Fixing Users",
                    description=f"Starting to fix {total_members} members with parallel processing..."
                )
            )

            fixed_count = 0
            error_count = 0
            rate_limited_count = 0
            start_time = time.time()

            max_workers = 10
            semaphore = asyncio.Semaphore(max_workers)

            async def fix_member(member):
                nonlocal fixed_count, error_count, rate_limited_count
                try:
                    async with semaphore:
                        try:
                            await fix(self.bot, member.id, guild.id)
                            fixed_count += 1
                        except discord.errors.HTTPException as http_err:
                            if http_err.code == 429:
                                rate_limited_count += 1
                                retry_after = getattr(http_err, 'retry_after', 5)
                                await asyncio.sleep(retry_after)
                                await fix(self.bot, member.id, guild.id)
                                fixed_count += 1
                            else:
                                error_count += 1
                                await self.error_handler.handle_error(http_err, f'fix member {member.id}')
                        except Exception as e:
                            error_count += 1
                            await self.error_handler.handle_error(e, f'fix member {member.id}')
                except Exception as e:
                    error_count += 1
                    await self.error_handler.handle_error(e, f'fix member {member.id}')

            batch_size = max_workers * 2
            for i in range(0, total_members, batch_size):
                batch = members[i:i + batch_size]
                tasks = [asyncio.create_task(fix_member(member)) for member in batch]
                await asyncio.gather(*tasks)

                elapsed_time = time.time() - start_time
                processed = fixed_count + error_count
                estimated_remaining = (elapsed_time / processed) * (total_members - processed) if processed > 0 else 0
                minutes, seconds = divmod(int(estimated_remaining), 60)
                remaining_time = f"{minutes}m {seconds}s"

                await progress_message.edit(
                    embed=self.embed_builder.build_info(
                        title="Fixing Users",
                        description=f"Processed {processed}/{total_members} members...\n"
                                    f"Success: {fixed_count} | Errors: {error_count} | Rate limits: {rate_limited_count}\n"
                                    f"Workers: {max_workers}\n"
                                    f"Estimated time remaining: {remaining_time}"
                    )
                )

            elapsed_time = time.time() - start_time
            minutes, seconds = divmod(int(elapsed_time), 60)
            total_time = f"{minutes}m {seconds}s"
            await progress_message.edit(
                embed=self.embed_builder.build_success(
                    title="Fix All Complete",
                    description=f"Successfully fixed {fixed_count} members.\n"
                                f"Errors encountered: {error_count}\n"
                                f"Rate limits hit: {rate_limited_count}\n"
                                f"Total time: {total_time}"
                )
            )

            
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
                        title='FixAll Run',
                        color=discord.Color.purple()
                    )
                    log_embed.add_field(name='Run By', value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                    log_embed.add_field(name='Guild', value=f"{ctx.guild.name} ({ctx.guild.id})", inline=True)
                    log_embed.add_field(name='Total Members', value=str(total_members), inline=True)
                    log_embed.add_field(name='Fixed', value=str(fixed_count), inline=True)
                    log_embed.add_field(name='Errors', value=str(error_count), inline=True)
                    log_embed.add_field(name='Rate Limits', value=str(rate_limited_count), inline=True)
                    log_embed.add_field(name='Time', value=f"<t:{int(time.time())}:F>", inline=True)
                    log_embed.set_footer(text=f"FixAll completed in {total_time}")
                    await mod_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                print(f"Failed to send modification log: {log_exc}")

        except Exception as e:
            await self.error_handler.handle_error(e, 'fixall command')
            embed = self.embed_builder.build_error(
                description='An error occurred while fixing all users. Please try again later.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(FixAll(bot))
