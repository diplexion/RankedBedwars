import discord
from discord.ext import commands
from discord import ui
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.fix import fix

class SettingsDropdown(ui.Select):
    def __init__(self, settings_data, author=None):
        self.settings_map = {
            'isprefixtoggled': 'Prefix Display',
            'ispartyinvitestoggled': 'Party Invites',
            'isscoringpingtoggled': 'Scoring Ping',
            'staticnickname': 'Static Nickname',
        }
        self._author = author
        options = [
            discord.SelectOption(
                label=display_name,
                value=setting_key,
                description=f'Currently: {"Enabled" if settings_data.get(setting_key, False) else "Disabled"}'
            )
            for setting_key, display_name in self.settings_map.items()
        ]
        super().__init__(
            placeholder='Choose a setting to modify',
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control these settings.", ephemeral=True)
            return
        selected_setting = self.values[0]
        view = self.view
        view.current_setting = selected_setting
        view.enable_button.disabled = False
        view.disable_button.disabled = False
        settings_data = interaction.client.database_manager.find_one(
            'settings',
            {'discordid': str(interaction.user.id)}
        ) or {}
        current_state = settings_data.get(selected_setting, False)
        view.enable_button.disabled = current_state
        view.disable_button.disabled = not current_state
        await interaction.response.edit_message(
            embed=interaction.client.embed_builder.build_info(
                title='Settings Manager',
                description=f'Selected: {self.settings_map[selected_setting]}\nCurrent Status: {"Enabled" if current_state else "Disabled"}'
            ),
            view=view
        )

class SettingsView(ui.View):
    def __init__(self, settings_data, author=None):
        super().__init__()
        self.current_setting = None
        self._author = author
        self.add_item(SettingsDropdown(settings_data, author=author))

        self.enable_button = ui.Button(style=discord.ButtonStyle.success, label='Enable', disabled=True)
        self.disable_button = ui.Button(style=discord.ButtonStyle.danger, label='Disable', disabled=True)

        async def enable_callback(interaction: discord.Interaction):
            if interaction.user != self._author:
                await interaction.response.send_message("You can't control these settings.", ephemeral=True)
                return
            if self.current_setting:
                interaction.client.database_manager.update_player_setting(
                    interaction.user.id,
                    self.current_setting,
                    True
                )
                await fix(interaction.client, interaction.user.id, interaction.guild_id)

                self.enable_button.disabled = True
                self.disable_button.disabled = False

                await interaction.response.edit_message(
                    embed=interaction.client.embed_builder.build_success(
                        title='Setting Updated',
                        description=f'Successfully enabled {self.children[0].settings_map[self.current_setting]}'
                    ),
                    view=self
                )

        async def disable_callback(interaction: discord.Interaction):
            if interaction.user != self._author:
                await interaction.response.send_message("You can't control these settings.", ephemeral=True)
                return
            if self.current_setting:
                interaction.client.database_manager.update_player_setting(
                    interaction.user.id,
                    self.current_setting,
                    False
                )
                await fix(interaction.client, interaction.user.id, interaction.guild_id)

                self.enable_button.disabled = False
                self.disable_button.disabled = True

                await interaction.response.edit_message(
                    embed=interaction.client.embed_builder.build_success(
                        title='Setting Updated',
                        description=f'Successfully disabled {self.children[0].settings_map[self.current_setting]}'
                    ),
                    view=self
                )

        self.enable_button.callback = enable_callback
        self.disable_button.callback = disable_callback

        self.add_item(self.enable_button)
        self.add_item(self.disable_button)

class PlayerSettings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='settings', help='Manage your player settings')
    async def settings(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('settings', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    ),
                    mention_author=False
                )
                return

            settings_data = self.bot.database_manager.find_one(
                'settings',
                {'discordid': str(ctx.author.id)}
            ) or {}

            view = SettingsView(settings_data, author=ctx.author)

            await ctx.reply(
                embed=self.embed_builder.build_info(
                    title='Settings Manager',
                    description='Select a setting from the dropdown menu below to modify it.'
                ),
                view=view,
                mention_author=False
            )

        except Exception as e:
            await self.error_handler.handle_error(e, 'settings command')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while loading settings. Please try again later.'
                ),
                mention_author=False
            )

async def setup(bot):
    await bot.add_cog(PlayerSettings(bot))
