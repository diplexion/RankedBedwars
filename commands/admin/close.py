import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.transcript_creator import create_transcript
import logging
import asyncio

logger = logging.getLogger(__name__)

class CloseScreenshare(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()

    @commands.command(name='close', help='Close an active screenshare session.\nUsage: !close <result> [evidence_url]')
    async def close_screenshare(self, ctx: commands.Context, result: str = None, evidence_url: str = None):
        try:
            if result is None:
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=close <result> [evidence_url]`\nExample: `=close clean https://i.imgur.com/evidence.png`'
                )
                await ctx.reply(embed=embed)
                return

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('close_screenshare', user_roles):
                await ctx.reply(embed=self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                ))
                return

            channel = ctx.channel
            if not channel:
                await ctx.reply(embed=self.embed_builder.build_error(
                    description='Could not determine the current channel.'
                ))
                return

            screenshare_info = self.bot.screenshare_manager.db.find_one('screenshares', {
                'state': 'in_progress',
                'channel_id': str(channel.id)
            })
            if not screenshare_info:
                await ctx.reply(embed=self.embed_builder.build_error(
                    description='No active screenshare session found in this channel.'
                ))
                return

            target_id = screenshare_info['target_id']
            guild = ctx.guild

            success, message = await self.bot.screenshare_manager.end_screenshare(
                target_id=target_id,
                result=result,
                channel_id=str(channel.id)
            )

            if not success:
                await ctx.reply(embed=self.embed_builder.build_error(
                    description=f'Error ending screenshare: {message}'
                ))
                return

            
            try:
                target_member = await guild.fetch_member(int(target_id))
                frozen_role = discord.utils.get(guild.roles, id=int(self.bot.config['roles']['frozen']))
                if frozen_role and frozen_role in target_member.roles:
                    await target_member.remove_roles(frozen_role)
            except Exception as e:
                logger.error(f'Error removing frozen role: {e}')

            embed = self.embed_builder.build_success(
                title='Screenshare Closed',
                description=f'Successfully closed screenshare session.\nResult: {result}\nChannel will be deleted in 60 seconds.'
            )
            await ctx.reply(embed=embed)

            await asyncio.sleep(60)

            
            try:
                await create_transcript(self.bot, channel.id, f"Screenshare for {target_member} Transcript")
            except Exception as transcript_error:
                logger.error(f'Error creating transcript for screenshare channel {channel.id}: {str(transcript_error)}')

            await asyncio.sleep(2)

            
            try:
                await channel.delete(reason=f'Screenshare closed: SS ended - Result: {result}')
            except Exception as e:
                logger.error(f'Error deleting channel: {e}')

        except Exception as e:
            logger.error(f"Error in close command: {e}")
            await self.error_handler.handle_error(e, 'close screenshare')
            await ctx.reply(embed=self.embed_builder.build_error(
                description=f'An error occurred while closing the screenshare: {str(e)}'
            ))

async def setup(bot):
    await bot.add_cog(CloseScreenshare(bot))
