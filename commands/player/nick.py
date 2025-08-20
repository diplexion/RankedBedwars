
import discord
from discord.ext import commands
from discord import ui
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.fix import fix

class NicknameView(ui.View):
    def __init__(self, current_nick, author=None):
        super().__init__()
        self._author = author
        self.current_nick = current_nick
        self.set_button = ui.Button(style=discord.ButtonStyle.success, label='Set Nickname', disabled=False)
        self.remove_button = ui.Button(style=discord.ButtonStyle.danger, label='Remove Nickname', disabled=(current_nick is None))

        async def set_callback(interaction: discord.Interaction):
            if interaction.user != self._author:
                await interaction.response.send_message("You can't control this menu.", ephemeral=True)
                return
            modal = NicknameModal(author=self._author, view=self)
            await interaction.response.send_modal(modal)

        async def remove_callback(interaction: discord.Interaction):
            if interaction.user != self._author:
                await interaction.response.send_message("You can't control this menu.", ephemeral=True)
                return
            db = interaction.client.database_manager
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild_id)
            user_data = db.find_one('settings', {'discordid': user_id})
            if user_data and user_data.get('nickname'):
                removed_nick = user_data['nickname']
                db.update_player_setting(user_id, 'nickname', None)
                await fix(interaction.client, user_id, guild_id)
                self.remove_button.disabled = True
                embed = interaction.client.embed_builder.build_success(
                    title='Nickname Removed',
                    description=f'Your nickname has been removed: **{removed_nick}**'
                )
            else:
                embed = interaction.client.embed_builder.build_warning(
                    title='No Nickname Found',
                    description="You don't have a nickname set."
                )
            await interaction.response.edit_message(embed=embed, view=self)

        self.set_button.callback = set_callback
        self.remove_button.callback = remove_callback
        self.add_item(self.set_button)
        self.add_item(self.remove_button)

class NicknameModal(ui.Modal, title="Set Nickname"):
    nickname = ui.TextInput(label="Enter your new nickname", min_length=1, max_length=32)

    def __init__(self, author, view):
        super().__init__()
        self._author = author
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this menu.", ephemeral=True)
            return
        db = interaction.client.database_manager
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        db.update_player_setting(user_id, 'nickname', self.nickname.value)
        await fix(interaction.client, user_id, guild_id)
        self._view.remove_button.disabled = False
        embed = interaction.client.embed_builder.build_success(
            title='Nickname Set',
            description=f'Your nickname has been changed to: **{self.nickname.value}**.'
        )
        await interaction.response.edit_message(embed=embed, view=self._view)

class Nickname(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='nick', help='Manage your nickname')
    async def nick(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('nick setnick', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    ),
                    mention_author=False
                )
                return

            db = self.bot.database_manager
            user_id = str(ctx.author.id)
            user_data = db.find_one('settings', {'discordid': user_id}) or {}
            current_nick = user_data.get('nickname')

            view = NicknameView(current_nick, author=ctx.author)

            await ctx.reply(
                embed=self.embed_builder.build_info(
                    title='Nickname Manager',
                    description=f'Current nickname: **{current_nick}**' if current_nick else 'You do not have a nickname set.'
                ),
                view=view,
                mention_author=False
            )

        except Exception as e:
            await self.error_handler.handle_error(e, 'nickname manager')
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    description='An error occurred while managing your nickname. Please try again later.'
                ),
                mention_author=False
            )

async def setup(bot):
    await bot.add_cog(Nickname(bot))
