import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import io
from typing import Optional
from bson import Timestamp
import mplcyberpunk


class StateSelect(discord.ui.Select):
    def __init__(self, parent_view, current_state):
        options = [
            discord.SelectOption(
                label="All", value="all", default=current_state == "all"
            ),
            discord.SelectOption(
                label="Scored", value="scored", default=current_state == "scored"
            ),
            discord.SelectOption(
                label="Voided", value="voided", default=current_state == "voided"
            ),
            discord.SelectOption(
                label="Pending", value="pending", default=current_state == "pending"
            ),
        ]
        super().__init__(placeholder="Select Game State", options=options, row=0)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.state = self.values[0]
        await self.parent_view.update_graph(interaction)


class IntervalSelect(discord.ui.Select):
    def __init__(self, parent_view, current_interval):
        options = [
            discord.SelectOption(
                label="1 Day", value="1", default=current_interval == 1
            ),
            discord.SelectOption(
                label="5 Days", value="5", default=current_interval == 5
            ),
            discord.SelectOption(
                label="10 Days", value="10", default=current_interval == 10
            ),
            discord.SelectOption(
                label="15 Days", value="15", default=current_interval == 15
            ),
            discord.SelectOption(
                label="30 Days", value="30", default=current_interval == 30
            ),
        ]
        super().__init__(placeholder="Select Interval", options=options, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.interval = int(self.values[0])
        await self.parent_view.update_graph(interaction)


class GamesCountView(discord.ui.View):
    def __init__(self, bot, db_manager, state="all", interval=5):
        super().__init__(timeout=120)
        self.bot = bot
        self.db_manager = db_manager
        self.state = state
        self.interval = interval
        self.add_item(StateSelect(self, self.state))
        self.add_item(IntervalSelect(self, self.interval))

    async def update_graph(self, interaction: discord.Interaction):
        file, embed = make_games_graph(
            self.db_manager, self.state, self.interval, self.bot
        )
        await interaction.response.edit_message(
            embed=embed, attachments=[file], view=self
        )


def make_games_graph(db_manager, state, interval, bot):
    now = datetime.utcnow()
    start_date = now - timedelta(days=interval)
    start_timestamp = Timestamp(int(start_date.timestamp()), 1)
    games = db_manager.find("games", {"date": {"$gte": start_timestamp}})

    date_buckets = [
        (start_date + timedelta(days=i)).date() for i in range(interval + 1)
    ]
    scored_counts = [0] * (interval + 1)
    voided_counts = [0] * (interval + 1)
    pending_counts = [0] * (interval + 1)

    for game in games:
        game_date = game.get("date")
        if not game_date:
            continue
        if hasattr(game_date, "as_datetime"):
            game_date = game_date.as_datetime().date()
        elif hasattr(game_date, "time") and hasattr(game_date, "inc"):
            game_date = datetime.utcfromtimestamp(game_date.time).date()
        elif isinstance(game_date, datetime):
            game_date = game_date.date()
        else:
            continue
        if not game_date or game_date < start_date.date():
            continue
        idx = (game_date - start_date.date()).days
        if idx < 0 or idx > interval:
            continue
        state_val = game.get("state", "unknown").lower()
        if state_val == "scored":
            scored_counts[idx] += 1
        elif state_val == "voided":
            voided_counts[idx] += 1
        elif state_val == "pending":
            pending_counts[idx] += 1

    if state != "all":
        match state:
            case "scored":
                voided_counts = [0] * (interval + 1)
                pending_counts = [0] * (interval + 1)
            case "voided":
                scored_counts = [0] * (interval + 1)
                pending_counts = [0] * (interval + 1)
            case "pending":
                scored_counts = [0] * (interval + 1)
                voided_counts = [0] * (interval + 1)
            # case _:
            # pass

    plt.style.use("cyberpunk")
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_facecolor("black")
    fig.patch.set_facecolor("black")

    ax.plot(date_buckets, scored_counts, marker="o", label="Scored", color="#43ea4a")
    ax.plot(date_buckets, voided_counts, marker="o", label="Voided", color="#ea4343")
    ax.plot(date_buckets, pending_counts, marker="o", label="Pending", color="#ffe14a")

    mplcyberpunk.add_glow_effects(ax)
    ax.set_xlabel("Date", color="white")
    ax.set_ylabel("Games", color="white")
    ax.set_title(
        "Games Count Over Time", fontsize=18, fontweight="bold", color="#43c6ea"
    )
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.tick_params(axis="x", labelrotation=30, labelsize=10, colors="white")
    ax.tick_params(axis="y", labelsize=10, colors="white")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", transparent=True)
    plt.close(fig)
    buf.seek(0)
    file = discord.File(buf, filename="games_graph.png")
    embed = bot.embed_builder.build_info(
        title="Games Count Graph",
        description=f"Showing {state.capitalize()} games for the last {interval} day(s). \n"
        f"Scored: {sum(scored_counts)} Voided: {sum(voided_counts)} Pending: {sum(pending_counts)}",
    )
    embed.set_image(url="attachment://games_graph.png")
    return file, embed


class AdminGamesCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(
        name="gamescount", help="Show a graph of games count by state and interval."
    )
    async def gamescount(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission("admingamescount", user_roles):
            embed = self.bot.embed_builder.build_error(
                title="Permission Denied",
                description="You do not have permission to use this command.",
            )
            await ctx.reply(embed=embed)
            return

        file, embed = make_games_graph(self.db_manager, "all", 5, self.bot)
        view = GamesCountView(self.bot, self.db_manager, state="all", interval=5)
        await ctx.reply(embed=embed, file=file, view=view)


def setup(bot):
    bot.add_cog(AdminGamesCount(bot))
