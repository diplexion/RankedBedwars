import discord
from discord.ext import commands
from discord import ui
from typing import Dict, Any, Callable
import yaml
import os
import random
import string
import asyncio
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.fix import fix

class VerificationModal(ui.Modal, title="Verify Minecraft Account"):
    verification_code = ui.TextInput(
        label="Verification Code",
        placeholder="Enter the code you received in-game",
        min_length=6,
        max_length=6,
        required=True
    )
    
    def __init__(self, callback: Callable):
        super().__init__()
        self.callback = callback
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.callback(interaction, self.verification_code.value)


class VerificationView(ui.View):
    def __init__(self, verify_callback: Callable, timeout: int = 600):
        super().__init__(timeout=timeout)
        self.verify_callback = verify_callback
    
    @ui.button(label="Enter Verification Code", style=discord.ButtonStyle.primary)
    async def verify_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = VerificationModal(self.verify_callback)
        await interaction.response.send_modal(modal)

class RenameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.config = self.load_config()
        
        
        self.websocket_enabled = self.config.get('websocket', {}).get('enabled', False)
        self.ws_manager = getattr(bot, 'websocket_manager', None) if self.websocket_enabled else None
        
        
        self.pending_verifications = {}  

    def load_config(self) -> Dict[str, Any]:
        config_path = os.path.join('configs', 'config.yml')
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.bot.logger.error(f"Failed to load configuration: {e}")
            raise
            
    def generate_verification_code(self) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    async def check_player_online(self, ign: str) -> bool:
        if not self.websocket_enabled or not self.ws_manager:
            return False
            
        try:
            player_handler = getattr(self.ws_manager, 'player_handler', None)
            if player_handler:
                return await player_handler.check_player_online(ign, timeout=10.0)
            return False
        except Exception as e:
            self.bot.logger.error(f"Error checking if player {ign} is online: {e}")
            return False
    
    async def send_verification_code(self, ign: str, code: str) -> bool:
        if not self.websocket_enabled or not self.ws_manager:
            return False
            
        try:
            
            verification_message = {
                'type': 'verification_code',
                'ign': ign,
                'code': code,
                'message': f"Your Discord verification code is: {code}"
            }
            
            
            if hasattr(self.ws_manager, 'broadcast'):
                await self.ws_manager.broadcast(verification_message)
                self.bot.logger.info(f"Sent verification code to {ign}: {code}")
                return True
            return False
        except Exception as e:
            self.bot.logger.error(f"Error sending verification code to {ign}: {e}")
            return False
            
    async def handle_verification_code_submit(self, interaction: discord.Interaction, code: str) -> None:
        user_id = str(interaction.user.id)
        
        if user_id not in self.pending_verifications:
            await interaction.followup.send(
                embed=self.embed_builder.build_error(
                    title="Verification Failed",
                    description="No verification pending. Please start the rename process again."
                ),
                ephemeral=True
            )
            return
            
        verification = self.pending_verifications[user_id]
        
        
        if verification.get("expires", 0) < discord.utils.utcnow().timestamp():
            del self.pending_verifications[user_id]
            await interaction.followup.send(
                embed=self.embed_builder.build_error(
                    title="Verification Expired",
                    description="Your verification code has expired. Please try again."
                ),
                ephemeral=True
            )
            return
            
        
        if verification["code"] != code:
            await interaction.followup.send(
                embed=self.embed_builder.build_error(
                    title="Invalid Code",
                    description="The verification code you entered is incorrect. Please try again."
                ),
                ephemeral=True
            )
            return
            
        
        new_ign = verification["new_ign"]
        old_ign = verification["old_ign"]
        
        
        update_result = self.bot.database_manager.update_player_ign(user_id, old_ign, new_ign)
        
        if update_result:
            await fix(self.bot, user_id, interaction.guild_id)
            success_embed = self.embed_builder.build_success(
                title='Rename Complete',
                description=f'Your IGN has been successfully updated to: **{new_ign}**.'
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
            
            try:
                config = self.config
                reg_log_channel_id = int(config.get('logging', {}).get('regandrename'))
                reg_log_channel = self.bot.get_channel(reg_log_channel_id)
                if reg_log_channel:
                    log_embed = discord.Embed(
                        title="User Rename (Verified)",
                        color=discord.Color.blue()
                    )
                    log_embed.add_field(name="User", value=f"<@{user_id}> ({user_id})", inline=True)
                    log_embed.add_field(name="Old IGN", value=f"`{old_ign}`", inline=True)
                    log_embed.add_field(name="New IGN", value=f"`{new_ign}`", inline=True)
                    log_embed.add_field(name="Method", value="WebSocket Verified", inline=True)
                    log_embed.set_footer(text=f"Guild ID: {interaction.guild_id}")
                    await reg_log_channel.send(embed=log_embed)
            except Exception as log_exc:
                print(f"Failed to send regandrename log: {log_exc}")
        else:
            await interaction.followup.send(
                embed=self.embed_builder.build_error(
                    description='An error occurred while renaming. Please try again later.'
                ),
                ephemeral=True
            )
        
        
        del self.pending_verifications[user_id]
        
    async def start_websocket_verification(self, ctx, current_ign: str, new_ign: str) -> bool:
        user_id = str(ctx.author.id)
        
        
        if not self.websocket_enabled or not self.ws_manager:
            return True
            
        
        is_online = await self.check_player_online(current_ign)
        if not is_online:
            error_embed = self.embed_builder.build_error(
                title="Player Not Online",
                description=f"You are not currently online on the server with IGN `{current_ign}`. Please join the server and try again."
            )
            
            await ctx.reply(embed=error_embed)
            return False
            
        
        verification_code = self.generate_verification_code()
        
        
        expiration = discord.utils.utcnow().timestamp() + 300  
        self.pending_verifications[user_id] = {
            "code": verification_code,
            "old_ign": current_ign,
            "new_ign": new_ign,
            "expires": expiration
        }
        
        
        sent = await self.send_verification_code(current_ign, verification_code)
        if not sent:
            error_embed = self.embed_builder.build_error(
                title="Verification Failed",
                description="Could not send verification code to you in-game. Please try again later."
            )
            
            await ctx.reply(embed=error_embed)
            
            
            del self.pending_verifications[user_id]
            return False
        
        
        verify_embed = self.embed_builder.build_info(
            title="Verification Required",
            description=(
                f"A verification code has been sent to `{current_ign}` in-game.\n\n"
                f"Please check your in-game chat and click the button below to enter the code.\n\n"
                f"This code will expire in 5 minutes."
            )
        )
        
        
        view = VerificationView(self.handle_verification_code_submit)
        
        await ctx.reply(embed=verify_embed, view=view)
        return False  

    async def rename_player(self, ctx: commands.Context, new_ign: str, verified: bool = False) -> None:
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            existing_ign = self.bot.database_manager.find_one(
                'users', {'ign': {'$regex': f'^{new_ign}$', '$options': 'i'}}
            )
            if existing_ign and str(existing_ign.get('discordid')) != user_id:
                embed = self.embed_builder.build_error(
                    title='IGN Taken',
                    description=f'The IGN `{new_ign}` is already taken by another user.'
                )
                await ctx.reply(embed=embed)
                return

            query = {'discordid': user_id}
            player = self.bot.database_manager.find_one('users', query)
            if not player:
                embed = self.embed_builder.build_error(
                    description='Could not find your user record. Please register first.'
                )
                await ctx.reply(embed=embed)
                return
                
            old_ign = player.get('ign', '')
            
            
            if not verified and self.websocket_enabled and self.ws_manager:
                started = await self.start_websocket_verification(ctx, old_ign, new_ign)
                if not started:
                    return  

            update_result = self.bot.database_manager.update_player_ign(user_id, old_ign, new_ign)

            if update_result:
                await fix(self.bot, user_id, guild_id)
                embed = self.embed_builder.build_success(
                    title='Rename Complete',
                    description=f'Your IGN has been successfully updated to: **{new_ign}**.'
                )
                await ctx.reply(embed=embed)
                
                try:
                    config = self.config
                    reg_log_channel_id = int(config.get('logging', {}).get('regandrename'))
                    reg_log_channel = self.bot.get_channel(reg_log_channel_id)
                    if reg_log_channel:
                        log_embed = discord.Embed(
                            title="User Rename",
                            color=discord.Color.blue()
                        )
                        log_embed.add_field(name="User", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                        log_embed.add_field(name="Old IGN", value=f"`{old_ign}`", inline=True)
                        log_embed.add_field(name="New IGN", value=f"`{new_ign}`", inline=True)
                        log_embed.add_field(name="Method", value="User Command", inline=True)
                        log_embed.set_footer(text=f"Guild ID: {guild_id}")
                        await reg_log_channel.send(embed=log_embed)
                except Exception as log_exc:
                    print(f"Failed to send regandrename log: {log_exc}")
            else:
                embed = self.embed_builder.build_error(
                    description='An error occurred while renaming. Please try again later.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'player renaming')
            embed = self.embed_builder.build_error(
                description='An error occurred while renaming. Please try again later.'
            )
            await ctx.reply(embed=embed)

    @commands.command(name='rename')
    async def rename(self, ctx: commands.Context, new_ign: str):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('rename', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        query = {'discordid': str(ctx.author.id)}
        player = self.bot.database_manager.find_one('users', query)

        if not player:
            embed = self.embed_builder.build_error(
                description=f'{ctx.author.mention}, you are not registered yet!'
            )
            await ctx.reply(embed=embed)
            return

        existing_ign = self.bot.database_manager.find_one(
            'users', {'ign': {'$regex': f'^{new_ign}$', '$options': 'i'}}
        )
        if existing_ign and str(existing_ign.get('discordid')) != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                title='IGN Taken',
                description=f'The IGN `{new_ign}` is already taken by another user.'
            )
            await ctx.reply(embed=embed)
            return

        await self.rename_player(ctx, new_ign)

async def setup(bot):
    await bot.add_cog(RenameCommands(bot))
