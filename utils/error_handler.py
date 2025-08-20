import discord
from discord.ext import commands
from typing import Optional, Union
import traceback
import sys
from managers.permission_manager import PermissionManager

class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()  

    async def handle_error(self, error: Exception, context: str = '') -> None:
        error_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self.bot.logger.error(f'Error in {context}: {error_trace}')
        
        try:
            channel_id = int(self.bot.config.get('logging', {}).get('error'))
            channel = self.bot.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Error Occurred",
                    description=f"Context: {context}\n```py\n{error_trace[-1800:]}```",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed)
        except Exception as e:
            self.bot.logger.error(f"Failed to send error embed to logging.error channel: {e}")

    async def handle_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            await self._send_error_embed(ctx, 'Command not found. Use !help to see available commands.')
        
        elif isinstance(error, commands.MissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self._send_error_embed(ctx, f'You need the following permissions to use this command: {perms}')
        
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self._send_error_embed(ctx, f'I need the following permissions to execute this command: {perms}')
        
        elif isinstance(error, commands.MissingRequiredArgument):
            await self._send_error_embed(ctx, f'Missing required argument: {error.param.name}')
        
        elif isinstance(error, commands.BadArgument):
            await self._send_error_embed(ctx, 'Invalid argument provided. Please check the command usage.')
        
        elif isinstance(error, commands.NoPrivateMessage):
            await self._send_error_embed(ctx, 'This command cannot be used in private messages.')
        
        elif isinstance(error, commands.CheckFailure):
            command_name = ctx.command.name
            required_roles = self.permission_manager.get_required_roles(command_name)
            roles_str = '\n - '.join([f"<@&{role_id}>" for role_id in required_roles]) if required_roles else 'None'
            await self._send_error_embed(ctx, f'You need to have atleast one of the following roles to execute this command\n - {roles_str}')
        
        elif isinstance(error, commands.CommandOnCooldown):
            await self._send_error_embed(ctx, f'This command is on cooldown. Try again in {error.retry_after:.2f} seconds.')
        
        elif isinstance(error, commands.MaxConcurrencyReached):
            await self._send_error_embed(ctx, f'Too many people using this command. Please wait.')
        
        elif isinstance(error, commands.DisabledCommand):
            await self._send_error_embed(ctx, 'This command is currently disabled.')
        
        else:
            
            error_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
            self.bot.logger.error(f'Unhandled command error: {error_trace}')
            
            try:
                channel_id = int(self.bot.config.get('logging', {}).get('error'))
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed = discord.Embed(
                        title="Command Error",
                        description=f"Command: {getattr(ctx.command, 'name', 'unknown')}\n```py\n{error_trace[-1800:]}```",
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed)
            except Exception as e:
                self.bot.logger.error(f"Failed to send command error embed to logging.error channel: {e}")
            await self._send_error_embed(ctx, 'An unexpected error occurred. Please try again later.')

    async def handle_interaction_error(self, interaction: discord.Interaction, error: Exception) -> None:
        if isinstance(error, discord.InteractionResponded):
            return  
        
        error_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        self.bot.logger.error(f'Interaction error: {error_trace}')
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send('An error occurred while processing your interaction.', ephemeral=True)
            else:
                await interaction.response.send_message('An error occurred while processing your interaction.', ephemeral=True)
        except Exception as e:
            self.bot.logger.error(f'Failed to send interaction error message: {e}')

    async def _send_error_embed(self, ctx: commands.Context, message: str) -> None:
        try:
            embed = self.bot.embed_builder.build_error(description=message)
            await ctx.reply(embed=embed)  
        except Exception as e:
            self.bot.logger.error(f'Failed to send error embed: {e}')
            try:
                await ctx.reply(f'Error: {message}')  
            except:
                pass  

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            await ctx.reply("Command not found! Use `=help` to see the available commands.")
        else:
            
            await ctx.reply(f"Unhandled exception: {error}")
