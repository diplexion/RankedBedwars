import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from typing import Optional

class AdminGamesPaginator(discord.ui.View):
    def __init__(self, bot, state, games, per_page=10):
        super().__init__(timeout=120)
        self.bot = bot
        self.state = state
        self.games = games
        self.per_page = per_page
        self.page = 0
        self.max_page = (len(games) - 1) // per_page
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.page > 0:
            self.add_item(self.PrevButton(self))
        if self.page < self.max_page:
            self.add_item(self.NextButton(self))

    def get_page_games(self):
        start = self.page * self.per_page
        end = start + self.per_page
        return self.games[start:end]

    async def update_message(self, interaction):
        game_list = []
        for game in self.get_page_games():
            game_state = game.get('state', 'unknown')
            game_list.append(f"Game #{game.get('gameid', 'N/A')} - State: {game_state.capitalize()}")
        game_list_str = '\n'.join(game_list)
        embed = self.bot.embed_builder.build_info(
            title=f'Recent Games ({self.state.capitalize()}) (Page {self.page+1}/{self.max_page+1})',
            description=game_list_str
        )
        await interaction.response.edit_message(embed=embed, view=self)

    class PrevButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label='Previous', row=0)
            self.view_ref = view
        async def callback(self, interaction: discord.Interaction):
            self.view_ref.page -= 1
            self.view_ref.update_buttons()
            await self.view_ref.update_message(interaction)

    class NextButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label='Next', row=0)
            self.view_ref = view
        async def callback(self, interaction: discord.Interaction):
            self.view_ref.page += 1
            self.view_ref.update_buttons()
            await self.view_ref.update_message(interaction)

class AdminGamesCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='admingames', help='View recently played games based on their state.')
    async def admingames(self, ctx, state: Optional[str] = "all"):
        try:
            valid_states = ['all', 'pending', 'scored', 'voided']
            state = state.lower()
            if state not in valid_states:
                await ctx.reply(f"Invalid state. Choose one of: `{', '.join(valid_states)}`.")
                return

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('admingames', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if state == "all":
                games_data = self.db_manager.find('games', {})
            else:
                games_data = self.db_manager.find('games', {'state': state})

            sorted_games = sorted(games_data, key=lambda x: int(x.get('id', 0) if x.get('id') else 0), reverse=True)

            if not sorted_games:
                embed = self.bot.embed_builder.build_error(
                    description=f'No games found with state: {state}.'
                )
                await ctx.reply(embed=embed)
                return

            if len(sorted_games) > 20:
                view = AdminGamesPaginator(self.bot, state, sorted_games)
                game_list = []
                for game in view.get_page_games():
                    game_state = game.get('state', 'unknown')
                    game_list.append(f"Game #{game.get('gameid', 'N/A')} - State: {game_state.capitalize()}")
                game_list_str = '\n'.join(game_list)
                embed = self.bot.embed_builder.build_info(
                    title=f'Recent Games ({state.capitalize()}) (Page 1/{view.max_page+1})',
                    description=game_list_str
                )
                await ctx.reply(embed=embed, view=view)
            else:
                game_list = []
                for game in sorted_games[:10]:
                    game_state = game.get('state', 'unknown')
                    game_list.append(f"Game #{game.get('gameid', 'N/A')} - State: {game_state.capitalize()}")
                game_list_str = '\n'.join(game_list)
                embed = self.bot.embed_builder.build_info(
                    title=f'Recent Games ({state.capitalize()})',
                    description=game_list_str
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'admingames command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while fetching games. Please try again later.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(AdminGamesCommands(bot))
