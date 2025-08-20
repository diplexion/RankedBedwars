import discord
from discord.ext import commands
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager
from managers.queue_processor import QueueProcessor
import time

class QueueStatusCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()
        self.queue_processor = QueueProcessor(bot)
        
    @commands.command(name='queuestatus', help='View the current status of all active queues.')
    async def queue_status(self, ctx):
        try:
            
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('queuestatus', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    )
                )
                return
                
            queues = self.queue_processor.db_manager.find('queues', {})
            if not queues:
                embed = self.embed_builder.build_info(
                    title='Queue Status',
                    description='No queues found in the database.'
                )
                await ctx.reply(embed=embed)
                return

            statuses = []
            for queue in queues:
                channel_id = queue['channelid']
                queue_name = f"<#{channel_id}>"
                status = self.queue_processor.get_queue_status(channel_id)
                
                if status['exists']:
                    wait_time_str = self._format_time(status['wait_time'])
                    can_start = "✅" if status['can_start_partial'] else "❌"
                    status_msg = (
                        f"**{queue_name}**\n"
                        f"Players: `{status['player_count']}/{status['max_players']}`\n"
                        f"Parties: `{status['parties']}`\n"
                        f"Wait Time: `{wait_time_str}`\n"
                        f"Ready for Partial: {can_start}\n"
                    )
                else:
                    status_msg = (
                        f"**{queue_name}**\n"
                        f"Status: `Inactive`\n"
                        f"Max Players: `{queue['maxplayers']}`\n"
                    )
                
                statuses.append(status_msg)

            chunks = [statuses[i:i + 5] for i in range(0, len(statuses), 5)]
            for i, chunk in enumerate(chunks):
                title = 'Queue Status' if i == 0 else f'Queue Status (Continued {i+1})'
                embed = self.embed_builder.build_info(
                    title=title,
                    description="\n\n".join(chunk)
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'get queue status')
            embed = self.embed_builder.build_error(
                description='An error occurred while retrieving queue statuses.'
            )
            await ctx.reply(embed=embed)

    def _format_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

async def setup(bot):
    await bot.add_cog(QueueStatusCommand(bot))
