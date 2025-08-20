import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class GamesPaginator(discord.ui.View):
    def __init__(self, bot, user_id, games, per_page=10):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id
        self.games = games
        self.per_page = per_page
        self.page = 0
        self.max_page = (len(games) - 1) // per_page
        self.message = None
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
            game_id = game.get('gameid', 'N/A')
            is_mvp = game.get('ismvp', False)
            result_emoji = {
                'win': '🟢',
                'lose': '🔴',
                'voided': '⚫',
                'pending': '🟡',
                'submitted': '⏳'
            }.get(game.get('result', ''), '❓')
            mvp_emoji = '🏆' if is_mvp else ''
            game_list.append(f"{result_emoji} [{game_id}](http://deyo.lol/thisshithasntmadeyet){mvp_emoji}")
        game_list_str = '\n'.join(game_list)
        embed = self.bot.embed_builder.build_info(
            title=f'Your Games (Page {self.page+1}/{self.max_page+1})',
            description=f"{game_list_str}"
        )
        await interaction.response.edit_message(embed=embed, view=self)

    class PrevButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label='Previous', row=0)
            self.view_ref = view
        async def callback(self, interaction):
            if interaction.user.id != int(self.view_ref.user_id):
                await interaction.response.send_message('You cannot control this pagination.', ephemeral=True)
                return
            self.view_ref.page -= 1
            self.view_ref.update_buttons()
            await self.view_ref.update_message(interaction)

    class NextButton(discord.ui.Button):
        def __init__(self, view):
            super().__init__(style=discord.ButtonStyle.primary, label='Next', row=0)
            self.view_ref = view
        async def callback(self, interaction):
            if interaction.user.id != int(self.view_ref.user_id):
                await interaction.response.send_message('You cannot control this pagination.', ephemeral=True)
                return
            self.view_ref.page += 1
            self.view_ref.update_buttons()
            await self.view_ref.update_message(interaction)

class GameCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='games')
    async def games(self, ctx, *, user: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('games', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if not user:
                user_id = str(ctx.author.id)
            else:
                if user.isdigit():
                    user_id = user
                elif user.startswith('<@') and user.endswith('>'):
                    user_id = user.strip('<@!>')
                else:
                    user_doc = self.db_manager.find_one('users', {'ign': {'$regex': f'^{user}$', '$options': 'i'}})
                    if user_doc:
                        user_id = user_doc['discordid']
                    else:
                        embed = self.bot.embed_builder.build_error(
                            description=f'No user found with IGN or ID: {user}.'
                        )
                        await ctx.reply(embed=embed)
                        return

            recent_games = self.db_manager.find('recentgames', {'discordid': user_id})
            sorted_games = sorted(recent_games, key=lambda x: int(x.get('id', 0) if x.get('id') else 0), reverse=True)

            if not sorted_games:
                embed = self.bot.embed_builder.build_error(
                    description='No recent games found for this user.'
                )
                await ctx.reply(embed=embed)
                return

            if len(sorted_games) > 15:
                view = GamesPaginator(self.bot, user_id, sorted_games)
                game_list = []
                for game in view.get_page_games():
                    game_id = game.get('gameid', 'N/A')
                    is_mvp = game.get('ismvp', False)
                    result_emoji = {
                        'win': '🟢',
                        'lose': '🔴',
                        'voided': '⚫',
                        'pending': '🟡',
                        'submitted': '⏳',
                        'mvp': '🏆'
                    }.get(game['result'], '❓')
                    mvp_emoji = '🏆' if is_mvp else ''
                    game_list.append(f"{result_emoji} [{game_id}](http://deyo.lol/thisshithasntmadeyet){mvp_emoji}")
                game_list_str = '\n'.join(game_list)
                embed = self.bot.embed_builder.build_info(
                    title=f'Recent Games (Page 1/{view.max_page+1})',
                    description=f"{game_list_str}"
                )
                await ctx.reply(embed=embed, view=view)
            else:
                game_list = []
                for game in sorted_games[:10]:
                    game_id = game.get('gameid', 'N/A')
                    is_mvp = game.get('ismvp', False)
                    result_emoji = {
                        'win': '🟢',
                        'lose': '🔴',
                        'voided': '⚫',
                        'pending': '🟡',
                        'submitted': '⏳'
                    }.get(game.get('result', ''), '❓')
                    mvp_emoji = '🏆' if is_mvp else ''
                    game_list.append(f"{result_emoji} [{game_id}](http://deyo.lol/thisshithasntmadeyet){mvp_emoji}")
                game_list_str = '\n'.join(game_list)
                embed = self.bot.embed_builder.build_info(
                    title='Recent Games',
                    description=f"{game_list_str}"
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'games command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while fetching recent games. Please try again later.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(GameCommands(bot))
