import discord
from discord.ext import commands
from discord import ui
from typing import Optional
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager
from utils.error_handler import ErrorHandler

class LeaderboardView(ui.View):
    def __init__(self, bot, stat_type="elo", page=0, author=None):
        super().__init__()
        self.bot = bot
        self.stat_type = stat_type
        self.page = page
        self.max_page = 0
        self.searched_player = None
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self._author = author
        self.update_leaderboard()

    def update_leaderboard(self):
        db_manager = DatabaseManager()
        self.all_players = db_manager.find('users', {})
        self.leaderboard = sorted(self.all_players, key=lambda user: user.get(self.stat_type, 0), reverse=True)
        
        paginated = self.leaderboard[self.page * 10:(self.page + 1) * 10]
        total = len(self.all_players)
        self.max_page = (total - 1) // 10
    
        lines = []
        for i, user in enumerate(paginated):
            pos = i + (self.page * 10)
            medal = self.get_medal(pos)
            line = f"{medal} {user['ign']} -> {user.get(self.stat_type, 0)}"
            if self.searched_player and user['ign'].lower() == self.searched_player.lower():
                line = f"**👉 {line}**"
            lines.append(line)

        self.embed = discord.Embed(
            title=f'Top {self.stat_type.capitalize()} Leaderboard',
            description='\n'.join(lines),
            color=discord.Color.blue()
        ).set_footer(text=f'Page {self.page + 1}/{self.max_page + 1} | Total Players: {total}')

    def get_medal(self, pos):
        medals = ['🥇', '🥈', '🥉']
        return medals[pos] if pos < 3 else f"#{pos + 1}"

    def get_page_for_position(self, pos: int) -> int:
        return (pos - 1) // 10

    def get_page_for_player(self, ign: str) -> int:
        try:
            idx = next(i for i, p in enumerate(self.leaderboard) if p['ign'].lower() == ign.lower())
            return idx // 10
        except StopIteration:
            return 0

    @ui.button(label='<', style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            return
        if self.page > 0:
            self.page -= 1
            self.update_leaderboard()
            await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(label='>', style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            return
        if self.page < self.max_page:
            self.page += 1
            self.update_leaderboard()
            await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(label='⟳', style=discord.ButtonStyle.green)
    async def reload(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            return
        self.update_leaderboard()
        await interaction.response.edit_message(embed=self.embed, view=self)

    @ui.button(emoji='🎯', style=discord.ButtonStyle.blurple)
    async def jump_to_position(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            return
        class PositionModal(ui.Modal, title='Jump to Position'):
            position = ui.TextInput(
                label='Enter position number',
                placeholder='Enter a number (1-999999)',
                required=True,
                min_length=1,
                max_length=6
            )
            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    pos = int(self.position.value)
                    if pos < 1:
                        raise ValueError
                    view.page = view.get_page_for_position(pos)
                    view.update_leaderboard()
                    await modal_interaction.response.edit_message(embed=view.embed, view=view)
                except:
                    await modal_interaction.response.send_message("Please enter a valid position number.", ephemeral=True)

        view = self
        await interaction.response.send_modal(PositionModal())

    @ui.button(emoji='🔍', style=discord.ButtonStyle.blurple)
    async def search_player(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self._author:
            await interaction.response.send_message("You can't control this leaderboard.", ephemeral=True)
            return
        class SearchModal(ui.Modal, title='Search Player'):
            ign = ui.TextInput(
                label='Enter player IGN',
                placeholder='Enter the player\'s name',
                required=True,
                min_length=1,
                max_length=16
            )
            async def on_submit(self, modal_interaction: discord.Interaction):
                view.searched_player = self.ign.value
                view.page = view.get_page_for_player(self.ign.value)
                view.update_leaderboard()
                await modal_interaction.response.edit_message(embed=view.embed, view=view)

        view = self
        await interaction.response.send_modal(SearchModal())


class PlayerLbCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='leaderboard', aliases=['lb'])
    async def leaderboard(self, ctx, category: Optional[str] = 'elo', identifier: Optional[str] = None):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('leaderboard', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            view = LeaderboardView(self.bot, stat_type=category, author=ctx.author)
            if identifier:
                view.searched_player = identifier
                view.page = view.get_page_for_player(identifier)
                view.update_leaderboard()
            await ctx.reply(embed=view.embed, view=view)

        except Exception as e:
            await self.error_handler.handle_error(e, 'display leaderboard')
            embed = self.embed_builder.build_error(
                description='An error occurred while displaying the leaderboard.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(PlayerLbCommands(bot))
