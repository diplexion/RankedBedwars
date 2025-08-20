import discord
from discord.ext import commands
import psutil
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager

class StatusCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()

    @commands.command(name='status', help='View the bot\'s current status and system information')
    async def status(self, ctx):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('status', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    ),
                    mention_author=False
                )
                return

            authors = (
                "<@919498122940547072> - Lead Dev\n <@166692371981926400> - Dev"
                
            )

            environment = (
                f"Bot `2.3.0`\n"
                f"Python `3.10.0`\n"
                f"discord.py `2.4.0`"
            )

            import datetime
            now = datetime.datetime.utcnow()
            bot_uptime = getattr(self.bot, 'uptime', None)
            if bot_uptime:
                delta = now - bot_uptime
                days, remainder = divmod(delta.total_seconds(), 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)
                uptime_str = f"{int(days)}d {int(hours)}h {int(minutes)}m"
            else:
                uptime_str = "?"

            
            queues = self.database_manager.find('queues', {})
            queue_lines = []
            for queue in queues:
                name = queue.get('name', queue.get('channelid', 'Unknown'))
                minelo = queue.get('minelo', 0)
                maxelo = queue.get('maxelo', 0)
                is_open = queue.get('isopen', True)
                emoji = '✅' if is_open else '❌'
                label = f"<#{queue.get('channelid')}>"
                queue_lines.append(f"{emoji} {label}")
            queues_block = '\n'.join(queue_lines) if queue_lines else 'No queues found.'


            embed = discord.Embed(title='Bot Info', color=discord.Color.green())
            embed.add_field(name='Authors', value=authors, inline=False)
            embed.add_field(name='Environment', value=environment, inline=False)
            embed.add_field(name='Uptime', value=uptime_str, inline=False)
            embed.add_field(name='Queues', value=queues_block, inline=False)
            embed.add_field(name='Source Code', value='[GitHub](http://deyo.lol)', inline=False)

            
            if self.bot.user and self.bot.user.display_avatar:
                embed.set_thumbnail(url=self.bot.user.display_avatar.url)

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Source Code', url='http://deyo.lol', style=discord.ButtonStyle.link))

            await ctx.reply(embed=embed, view=view, mention_author=False)

        except Exception as e:
            await self.error_handler.handle_error(e, 'status command')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while retrieving bot status. Please try again later.'
                ),
                mention_author=False
            )

async def setup(bot):
    await bot.add_cog(StatusCommands(bot))
