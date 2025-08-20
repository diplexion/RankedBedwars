import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from actions.scoring import scoring

class ScoreGameCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='score', help='Score a game', aliases=['scoregame'])
    async def score(self, ctx, gameid: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('score', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            if not gameid:
                game_channel = self.bot.database_manager.find_one('gameschannels', {'textchannelid': str(ctx.channel.id)})
                if not game_channel:
                    embed = self.embed_builder.build_error(
                        title='Game ID Not Found',
                        description='No game is associated with this channel.'
                    )
                    await ctx.reply(embed=embed)
                    return
                gameid = game_channel.get('gameid')

            gameid = gameid.upper()
            existing_game = self.bot.database_manager.find_one('games', {'gameid': gameid})
            if not existing_game:
                embed = self.embed_builder.build_error(
                    title='Game Not Found',
                    description=f'No game found with ID `{gameid}`.'
                )
                await ctx.reply(embed=embed)
                return

            
            class TeamSelectionView(discord.ui.View):
                def __init__(self, author, bot, game_data, timeout=60):
                    super().__init__(timeout=timeout)
                    self.author = author
                    self.bot = bot
                    self.team_selected = None
                    self.mvp_selected = []
                    self.bedbreaker_selected = []
                    
                    
                    all_players = game_data.get('team1', []) + game_data.get('team2', [])
                    self.player_igns = []
                    for player_id in all_players:
                        user = self.bot.database_manager.find_one('users', {'discordid': player_id})
                        if user and 'ign' in user:
                            self.player_igns.append(discord.SelectOption(label=user['ign'], value=player_id))
                    
                    
                    self.select_mvps.options = self.player_igns
                    self.select_bedbreakers.options = self.player_igns

                async def interaction_check(self, interaction: discord.Interaction) -> bool:
                    if interaction.user.id != self.author.id:
                        await interaction.response.send_message("Only the command sender can interact.", ephemeral=True)
                        return False
                    return True

                @discord.ui.button(label="Team 1", style=discord.ButtonStyle.blurple)
                async def select_team1(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.team_selected = 1
                    await interaction.response.send_message("Team 1 selected.", ephemeral=True)

                @discord.ui.button(label="Team 2", style=discord.ButtonStyle.blurple)
                async def select_team2(self, interaction: discord.Interaction, button: discord.ui.Button):
                    self.team_selected = 2
                    await interaction.response.send_message("Team 2 selected.", ephemeral=True)

                @discord.ui.select(placeholder="Select MVPs (top kill) [optional]", min_values=0, max_values=5)
                async def select_mvps(self, interaction: discord.Interaction, select: discord.ui.Select):
                    self.mvp_selected = select.values
                    selected_igns = [opt.label for opt in self.player_igns if opt.value in select.values]
                    await interaction.response.send_message(f"Selected MVPs: {', '.join(selected_igns) or 'None'}", ephemeral=True)

                @discord.ui.select(placeholder="Select Bed Breakers [optional]", min_values=0, max_values=5)
                async def select_bedbreakers(self, interaction: discord.Interaction, select: discord.ui.Select):
                    self.bedbreaker_selected = select.values
                    selected_igns = [opt.label for opt in self.player_igns if opt.value in select.values]
                    await interaction.response.send_message(f"Selected Bed Breakers: {', '.join(selected_igns) or 'None'}", ephemeral=True)

                @discord.ui.button(label="Score Game", style=discord.ButtonStyle.green)
                async def score_game(self, interaction: discord.Interaction, button: discord.ui.Button):
                    if not self.team_selected:
                        await interaction.response.send_message("Please select a winning team.", ephemeral=True)
                        return
                    self.stop()
                    await interaction.response.defer()

            view = TeamSelectionView(ctx.author, self.bot, existing_game)
            embed = discord.Embed(
                title="Score Game",
                description=f"Game ID: `{gameid}`\nSelect the winning team, MVPs, and bed breakers.",
                color=discord.Color.orange()
            )
            
            
            team1_igns = []
            team2_igns = []
            for player_id in existing_game.get('team1', []):
                user = self.bot.database_manager.find_one('users', {'discordid': player_id})
                if user and 'ign' in user:
                    team1_igns.append(user['ign'])
            for player_id in existing_game.get('team2', []):
                user = self.bot.database_manager.find_one('users', {'discordid': player_id})
                if user and 'ign' in user:
                    team2_igns.append(user['ign'])
                    
            embed.add_field(name="Team 1", value="\n".join(team1_igns) or "No players", inline=True)
            embed.add_field(name="Team 2", value="\n".join(team2_igns) or "No players", inline=True)
            
            msg = await ctx.reply(embed=embed, view=view)
            await view.wait()

            try:
                await msg.edit(view=None)
            except Exception:
                pass

            if not view.team_selected:
                timeout_embed = self.embed_builder.build_error(
                    description='Scoring timed out. Please try again.'
                )
                await ctx.reply(embed=timeout_embed)
                return

            
            mvp_discord_ids = []
            bedbreaker_discord_ids = []

            mvp_discord_ids = view.mvp_selected
            bedbreaker_discord_ids = view.bedbreaker_selected
            
            
            mvp_igns = [opt.label for opt in view.player_igns if opt.value in mvp_discord_ids]
            bedbreaker_igns = [opt.label for opt in view.player_igns if opt.value in bedbreaker_discord_ids]

            await scoring(
                bot=self.bot,
                gameid=gameid,
                winningteamnumber=view.team_selected,
                mvp_ids=mvp_discord_ids,
                bedbreaker_ids=bedbreaker_discord_ids,
                scoredby=ctx.author.id
            )

            success_embed = self.embed_builder.build_success(
                title="Game Scored Successfully",
                description=f"Game ID: `{gameid}`\nWinning Team: Team {view.team_selected}\nMVPs: {', '.join(mvp_igns)}\nBed Breakers: {', '.join(bedbreaker_igns)}"
            )
            await ctx.reply(embed=success_embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'score command')
            error_embed = self.embed_builder.build_error(
                description='An error occurred while scoring the game.'
            )
            await ctx.reply(embed=error_embed)

def setup(bot):
    bot.add_cog(ScoreGameCommand(bot))
