import discord
from discord.ext import commands
from discord import ui
from typing import Optional
from datetime import datetime
import yaml
import os
import asyncio
import logging

from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

logger = logging.getLogger(__name__)

class FreezeButton(ui.Button):
    def __init__(self, target_id: int):
        super().__init__(
            style=discord.ButtonStyle.danger,
            label='Freeze',
            custom_id=f'freeze_button_{target_id}'
        )
        self.target_id = target_id

    async def callback(self, interaction: discord.Interaction):
        if not PermissionManager().has_permission('screensharer', [role.id for role in interaction.user.roles]):
            await interaction.response.send_message(
                embed=interaction.client.embed_builder.build_error(
                    description='You do not have permission to freeze users.'
                ),
                ephemeral=True
            )
            return

        try:
            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)

            frozen_role_id = config['roles']['frozen']
            category_id = config['categories']['screenshare']

            guild = interaction.guild
            target = guild.get_member(self.target_id)
            if not target:
                await interaction.response.send_message(
                    embed=interaction.client.embed_builder.build_error(
                        description='Target user not found in the server.'
                    ),
                    ephemeral=True
                )
                return

            screenshare_info = interaction.client.screenshare_manager.get_screenshare_info(str(self.target_id))
            if not screenshare_info or screenshare_info['state'] != 'pending':
                await interaction.response.send_message(
                    embed=interaction.client.embed_builder.build_error(
                        description='No active pending screenshare found for this user.'
                    ),
                    ephemeral=True
                )
                return

            category = guild.get_channel(int(category_id))
            channel = await guild.create_text_channel(
                name=f'screenshare-{target.name.lower()}',
                category=category,
                overwrites={
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    target: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
            )

            frozen_role = guild.get_role(int(frozen_role_id))
            if frozen_role:
                try:
                    await target.add_roles(frozen_role)
                except Exception as e:
                    logger.error(f"Error adding frozen role: {e}")
                    await channel.send(f"Warning: Failed to add frozen role to {target.mention}")

            await interaction.client.screenshare_manager.assign_screensharer(
                str(self.target_id), str(interaction.user.id)
            )
            await interaction.client.screenshare_manager.update_channel_id(
                str(self.target_id), str(channel.id)
            )

            server_ip = config['server']['serverip']
            
            
            websocket_enabled = config.get('websocket', {}).get('enabled', False)
            notification_message = ""
            
            if websocket_enabled:
                
                player_data = interaction.client.database_manager.find_one('users', {'discordid': str(self.target_id)})
                if player_data and player_data.get('ign'):
                    notification_message = "\n\n✅ **Player has been notified in-game via WebSocket**"
                else:
                    notification_message = "\n\n❌ **Could not notify player in-game (IGN not found)**"
            
            await channel.send(
                content=(
                    f'{target.mention}, you have been frozen by {interaction.user.mention}.{notification_message}\n\n'
                    '****YOU ARE FROZEN YOU HAVE 5 MINUTES TO DOWNLOAD ANYDESK****\n'
                    '> **What Should You Do ?**\n\n'
                    f'> #1 Don\'t Log Out the Server `{server_ip}`\n'
                    '> #2 Don\'t Unplug or plug any devices such as mouses/keyboards/usbs/etc..\n'
                    '> #3 Don\'t Delete Rename Or Modify any file in your PC\n\n'
                    '> Refuse to SS ***14d Ban***\n'
                    '> Admit to cheating ***14d Ban***\n'
                    '> Get ScreenShared ***if broken rules found you will be punished***\n'
                    '> AnyDesk | https://anydesk.com/en'
                )
            )

            await interaction.response.send_message(
                embed=interaction.client.embed_builder.build_success(
                    description=f'Successfully froze {target.mention}. Channel created: {channel.mention}'
                ),
                ephemeral=True
            )

            self.disabled = True
            await interaction.message.edit(view=self.view)

        except Exception as e:
            logger.error(f"Error in freeze button callback: {e}")
            await interaction.response.send_message(
                embed=interaction.client.embed_builder.build_error(
                    description=f'An error occurred while processing the freeze command: {str(e)}'
                ),
                ephemeral=True
            )


class PlayerSSCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='screenshare', aliases=['ss'])
    async def screenshare(self, ctx: commands.Context, target: discord.Member, *, reason: str = None):
        try:
            if not ctx.message.attachments:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        description='Please attach an image as evidence.'
                    )
                )
                return

            evidence = ctx.message.attachments[0]
            if not evidence.content_type or not evidence.content_type.startswith('image/'):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        description='Only image attachments are allowed.'
                    )
                )
                return

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('screenshare', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    )
                )
                return

            success, message = await self.bot.screenshare_manager.create_screenshare(
                target_id=str(target.id),
                requester_id=str(ctx.author.id),
                reason=reason or "No reason provided",
                image_url=evidence.url
            )

            if not success:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        description=f'Failed to create screenshare: {message}'
                    )
                )
                return

            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)

            channel_id = config['channels']['screenshare']
            screensharer_role_id = config['roles'].get('screensharer')
            channel = self.bot.get_channel(int(channel_id))

            roleping = ''
            if screensharer_role_id:
                screensharer_role = ctx.guild.get_role(int(screensharer_role_id))
                if screensharer_role:
                    roleping = screensharer_role.mention

            embed = discord.Embed(
                title='New Screenshare Request',
                description=f'**Target:** {target.mention}\n'
                            f'**Requester:** {ctx.author.mention}\n'
                            f'**Reason:** {reason or "N/A"}',
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            
            
            websocket_enabled = config.get('websocket', {}).get('enabled', False)
            if websocket_enabled:
                
                player_data = self.bot.database_manager.find_one('users', {'discordid': str(target.id)})
                if player_data and player_data.get('ign'):
                    embed.add_field(
                        name="In-game Notification", 
                        value="✅ Player has been notified in-game", 
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="In-game Notification", 
                        value="❌ Could not notify player (IGN not found)", 
                        inline=False
                    )
            
            embed.set_image(url=evidence.url)

            view = discord.ui.View()
            view.add_item(FreezeButton(target.id))

            await channel.send(content=roleping, embed=embed, view=view)

            await ctx.reply(
                embed=self.embed_builder.build_success(
                    title='Screenshare Requested',
                    description=f'Successfully requested screenshare for {target.mention}.'
                )
            )

        except Exception as e:
            logger.error(f"Error in screenshare command: {e}")
            await self.error_handler.handle_error(e, 'screenshare command')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while processing the screenshare request.'
                )
            )

async def setup(bot):
    await bot.add_cog(PlayerSSCommands(bot))
