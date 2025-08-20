import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from actions.voiding import void

class CancelGameView(discord.ui.View):
    def __init__(self, bot, game_id, team1, team2):
        super().__init__(timeout=150) 
        self.bot = bot
        self.game_id = game_id
        self.team1 = team1
        self.team2 = team2
        self.upvotes = 0
        self.downvotes = 0
        self.voters = set()
        self.message = None

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        channel = self.bot.get_channel(int(self.bot.config['channels']['games']))
        total_votes = self.upvotes + self.downvotes
        if total_votes > 2:
            if self.upvotes > self.downvotes:
                await void(self.bot, self.game_id)
                result_embed = discord.Embed(
                    title="Vote Results",
                    description=f"Game {self.game_id} has been cancelled by majority vote.\nUpvotes: {self.upvotes}\nDownvotes: {self.downvotes}",
                    color=discord.Color.green()
                )
            else:
                result_embed = discord.Embed(
                    title="Vote Results",
                    description=f"Game {self.game_id} will continue as the majority voted against cancellation.\nUpvotes: {self.upvotes}\nDownvotes: {self.downvotes}",
                    color=discord.Color.red()
                )
        else:
            result_embed = discord.Embed(
                title="Vote Results",
                description=f"Not enough votes were cast to decide. At least 3 votes are required.\nUpvotes: {self.upvotes}\nDownvotes: {self.downvotes}",
                color=discord.Color.orange()
            )

        if self.message:
            await self.message.edit(embed=result_embed, view=self)
        if channel and (not self.message or channel.id != self.message.channel.id):
            await channel.send(embed=result_embed)

    @discord.ui.button(label="Upvote", style=discord.ButtonStyle.green)
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.team1 + self.team2:
            await interaction.response.send_message("You are not part of this game.", ephemeral=True)
            return

        if interaction.user.id in self.voters:
            await interaction.response.send_message("You have already voted.", ephemeral=True)
            return

        self.upvotes += 1
        self.voters.add(interaction.user.id)
        await interaction.response.send_message("Your upvote has been recorded.", ephemeral=True)

        embed = interaction.message.embeds[0]
        embed.description = f"A vote has been started to cancel game {self.game_id}.\nOnly players from this game can vote.\nThe vote will last for 2 minutes and 30 seconds.\n\nCurrent Votes:\nUpvotes: {self.upvotes}\nDownvotes: {self.downvotes}"
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Downvote", style=discord.ButtonStyle.red)
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.team1 + self.team2:
            await interaction.response.send_message("You are not part of this game.", ephemeral=True)
            return

        if interaction.user.id in self.voters:
            await interaction.response.send_message("You have already voted.", ephemeral=True)
            return

        self.downvotes += 1
        self.voters.add(interaction.user.id)
        await interaction.response.send_message("Your downvote has been recorded.", ephemeral=True)

        embed = interaction.message.embeds[0]
        embed.description = f"A vote has been started to cancel game {self.game_id}.\nOnly players from this game can vote.\nThe vote will last for 2 minutes and 30 seconds.\n\nCurrent Votes:\nUpvotes: {self.upvotes}\nDownvotes: {self.downvotes}"
        await interaction.message.edit(embed=embed)

class CancelGameCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name="cancel", help="Start a vote to cancel a game. Optional game_id.")
    async def cancel(self, ctx, game_id: str = None):
        if not isinstance(ctx.author, discord.Member):
            return

        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('cancel', user_roles):
            embed = discord.Embed(
                title='Permission Denied',
                description='You do not have permission to use this command.',
                color=discord.Color.red()
            )
            await ctx.reply(embed=embed)
            return

        if not game_id:
            current_channel_id = str(ctx.channel.id)
            game_channel = self.db_manager.find_one('gameschannels', {'textchannelid': current_channel_id})

            if not game_channel:
                embed = discord.Embed(
                    title='Error',
                    description='Please provide a game ID or use this command in a game channel.',
                    color=discord.Color.red()
                )
                await ctx.reply(embed=embed)
                return

            game_id = game_channel.get('gameid')
        else:
            game_id = game_id.upper()

        game = self.db_manager.find_one("games", {"gameid": game_id})
        if not game:
            await ctx.reply("Game not found.")
            return

        team1 = [int(player_id) for player_id in game.get("team1", [])]
        team2 = [int(player_id) for player_id in game.get("team2", [])]

        view = CancelGameView(self.bot, game_id, team1, team2)
        embed = discord.Embed(
            title="Vote to Cancel Game",
            description=(
                f"A vote has been started to cancel game {game_id}.\n"
                f"Only players from this game can vote.\n"
                f"The vote will last for 2 minutes and 30 seconds.\n\n"
                f"Current Votes:\n"
                f"Upvotes: 0\n"
                f"Downvotes: 0"
            ),
            color=discord.Color.orange()
        )
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

def setup(bot):
    bot.add_cog(CancelGameCommand(bot))
