from managers.database_manager import DatabaseManager
import discord
from utils.discord_utils import delete_channel
from actions.fix import fix
from utils.embed_builder import EmbedBuilder
from actions.transcript_creator import create_transcript
import yaml
import asyncio
from datetime import datetime
import time
from bson import Timestamp


async def void(bot, gameid, staffid=None):
    db_manager = DatabaseManager()
    embed_builder = EmbedBuilder()
    bot = bot
    try:
        with open("configs/config.yml", "r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
            guild_id = int(config["bot"]["guildid"])

        voiding_log_channel = None
        try:
            voiding_log_channel_id = int(config.get("logging", {}).get("voiding"))
            voiding_log_channel = bot.get_channel(voiding_log_channel_id)
        except Exception as e:
            print(f"Could not get logging.voiding channel: {e}")

        game = db_manager.find_one("games", {"gameid": gameid})
        if not game:
            print(f"Game with gameid {gameid} not found.")

            if voiding_log_channel:
                embed = discord.Embed(
                    title="Voiding Attempt Failed",
                    description=f"Game with gameid `{gameid}` not found.",
                    color=discord.Color.red(),
                )
                await voiding_log_channel.send(embed=embed)
            return

        if game.get("state") == "voided":
            print(f"Game state is not eligible for voiding: {game.get('state')}")

            if voiding_log_channel:
                embed = discord.Embed(
                    title="Voiding Attempt Failed",
                    description=f"Game `{gameid}` is already voided.",
                    color=discord.Color.red(),
                )
                await voiding_log_channel.send(embed=embed)
            return

        recent_games = db_manager.find("recentgames", {"gameid": gameid})
        if not recent_games:
            print(f"No recent games found for gameid {gameid}.")

            if voiding_log_channel:
                embed = discord.Embed(
                    title="Voiding Attempt Failed",
                    description=f"No recent games found for gameid `{gameid}`.",
                    color=discord.Color.red(),
                )
                await voiding_log_channel.send(embed=embed)
            return

        if voiding_log_channel:
            try:
                team1_ids = game.get("team1", [])
                team2_ids = game.get("team2", [])
                staff_mention = f"<@{staffid}>" if staffid else "System"
                affected_users = [
                    f"<@{g.get('discordid')}>: {g.get('result')}" for g in recent_games
                ]
                embed = discord.Embed(
                    title=f"Game Voided: {gameid}", color=discord.Color.orange()
                )
                embed.add_field(name="Game ID", value=f"`{gameid}`", inline=True)
                embed.add_field(
                    name="State", value=f"{game.get('state', 'unknown')}", inline=True
                )
                embed.add_field(
                    name="Team 1",
                    value=(", ".join([f"<@{pid}>" for pid in team1_ids]) or "None"),
                    inline=False,
                )
                embed.add_field(
                    name="Team 2",
                    value=(", ".join([f"<@{pid}>" for pid in team2_ids]) or "None"),
                    inline=False,
                )
                embed.add_field(name="Voided By", value=staff_mention, inline=True)
                embed.add_field(
                    name="Affected Users",
                    value="\n".join(affected_users) or "None",
                    inline=False,
                )
                await voiding_log_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send voiding log embed: {e}")

        db_manager.db["recentgames"].update_many(
            {"gameid": gameid},
            {
                "$set": {
                    "ismvp": False,
                    "result": "voided",
                    "elochange": 0,
                    "kills": "0",
                    "deaths": "0",
                    "bedbroke": False,
                    "finalkills": 0,
                    "diamonds": 0,
                    "irons": 0,
                    "gold": 0,
                    "emeralds": 0,
                    "blocksplaced": 0,
                    "state": "voided",
                }
            },
        )
        print(f"Reset MVP status and stats for all players in game {gameid}.")

        for recent_game in recent_games:
            player_id = recent_game.get("discordid")
            elo_change = recent_game.get("elochange", 0)

            user = db_manager.find_one("users", {"discordid": str(player_id)})
            if user:
                current_elo = user.get("elo", 0)
                new_elo = max(0, current_elo - elo_change)

                wins = user.get("wins", 0)
                losses = user.get("losses", 0)
                winstreak = user.get("winstreak", 0)
                loosestreak = user.get("loosestreak", 0)
                highest_elo = user.get("highest_elo", 0)
                highest_winstreak = user.get("highstwinstreak", 0)

                if recent_game.get("result") == "win":
                    wins -= 1
                    winstreak = max(0, winstreak - 1)
                elif recent_game.get("result") == "loss":
                    losses -= 1
                    loosestreak = max(0, loosestreak - 1)

                if recent_game.get("ismvp", False):
                    current_mvp_count = user.get("mvps", 0)
                    if current_mvp_count > 0:
                        db_manager.db["users"].update_one(
                            {"discordid": str(player_id)}, {"$inc": {"mvps": -1}}
                        )
                        print(f"Decremented MVP count for user {player_id}")

                kills = user.get("kills", 0)
                deaths = user.get("deaths", 0)
                beds_broken = user.get("bedsbroken", 0)
                finalkills = user.get("finalkills", 0)
                diamonds = user.get("diamonds", 0)
                irons = user.get("irons", 0)
                gold = user.get("gold", 0)
                emeralds = user.get("emeralds", 0)
                blocksplaced = user.get("blocksplaced", 0)

                with open("configs/config.yml", "r", encoding="utf-8") as file:
                    config = yaml.safe_load(file)
                    websocket_enabled = config.get("websocket", {}).get(
                        "enabled", False
                    )

                if recent_game.get("kills"):
                    kills -= int(recent_game.get("kills", 0))
                if recent_game.get("deaths"):
                    deaths -= int(recent_game.get("deaths", 0))
                if recent_game.get("bedbroke") is True:
                    beds_broken -= 1

                if websocket_enabled:
                    stats = {
                        "finalkills": finalkills,
                        "diamonds": diamonds,
                        "irons": irons,
                        "gold": gold,
                        "emeralds": emeralds,
                        "blocksplaced": blocksplaced,
                    }

                    for key in stats:
                        if recent_game.get(key):
                            stats[key] -= int(recent_game[key])

                    finalkills = stats["finalkills"]
                    diamonds = stats["diamonds"]
                    irons = stats["irons"]
                    gold = stats["gold"]
                    emeralds = stats["emeralds"]
                    blocksplaced = stats["blocksplaced"]

                db_manager.db["users"].update_one(
                    {"discordid": str(player_id)},
                    {
                        "$set": {
                            "elo": new_elo,
                            "wins": wins,
                            "losses": losses,
                            "winstreak": winstreak,
                            "loosestreak": loosestreak,
                            "highest_elo": max(highest_elo, new_elo),
                            "highstwinstreak": max(highest_winstreak, winstreak),
                            "kills": max(0, kills),
                            "deaths": max(0, deaths),
                            "bedsbroken": max(0, beds_broken),
                            "finalkills": max(0, finalkills),
                            "diamonds": max(0, diamonds),
                            "irons": max(0, irons),
                            "gold": max(0, gold),
                            "emeralds": max(0, emeralds),
                            "blocksplaced": max(0, blocksplaced),
                        }
                    },
                )
                print(
                    f"Reverted elo and stats for user {player_id}: {new_elo}, wins: {wins}, losses: {losses}"
                )

                guild_id = config["bot"]["guildid"]

                await fix(bot, player_id, guild_id)

            db_manager.db["recentgames"].update_one(
                {"gameid": gameid, "discordid": str(player_id)},
                {
                    "$set": {
                        "result": "voided",
                        "elochange": 0,
                        "kills": "0",
                        "deaths": "0",
                        "bedbroke": False,
                        "finalkills": 0,
                        "diamonds": 0,
                        "irons": 0,
                        "gold": 0,
                        "emeralds": 0,
                        "blocksplaced": 0,
                        "state": "voided",
                    }
                },
            )
            print(
                f"Updated recentgames for player {player_id} in game {gameid} to voided."
            )

        db_manager.db["games"].update_one(
            {"gameid": gameid},
            {
                "$set": {
                    "state": "voided",
                    "end_time": Timestamp(int(time.time()), 1),
                    "mvps": [],
                }
            },
        )
        print(
            f"Updated game state for gameid {gameid} to voided and cleared MVPs list."
        )

        game_channels = db_manager.find_one("gameschannels", {"gameid": gameid})
        if game_channels:
            text_channel_id = game_channels.get("textchannelid")
            team1_voice_channel_id = game_channels.get("team1voicechannelid")
            team2_voice_channel_id = game_channels.get("team2voicechannelid")

            description = f"The game with ID {gameid} has been voided by {f'<@{staffid}>' if staffid else 'System'}. All ELO changes have been reverted.\n"
            mention = ""

            for player_id in game["team1"]:
                mention += f" <@{player_id}> "
            for player_id in game["team2"]:
                mention += f" <@{player_id}> "

            embed = embed_builder.build_info(
                title="Game Voided", description=description
            )

            embed2 = embed_builder.build_info(
                title="Channel Deletion Notice",
                description="This channel will be deleted in 30 seconds.",
            )

            gameschannelid = config["channels"]["scoring"]
            games_channel = bot.get_channel(int(gameschannelid))
            text_channel = bot.get_channel(int(text_channel_id))
            if games_channel:
                await games_channel.send(content=f"{mention}", embed=embed)

            else:
                print(f"Games channel with ID {gameschannelid} not found")
            if text_channel:
                await text_channel.send(embed=embed)
                await text_channel.send(embed=embed2)
            else:
                print(f"Text channel with ID {text_channel_id} not found")
            try:
                await asyncio.sleep(30)
                try:
                    await asyncio.create_task(
                        create_transcript(
                            bot, int(text_channel_id), f"Game #{gameid} Transcript"
                        )
                    )
                except Exception as transcript_error:
                    print(
                        f"Error creating transcript for game {gameid}: {str(transcript_error)}"
                    )

                guild_id = int(bot.config["bot"]["guildid"])
                guild = bot.get_guild(guild_id)
                if not guild:
                    print(f"Guild with ID {guild_id} not found.")
                    return

                if text_channel_id:
                    try:
                        await asyncio.create_task(
                            delete_channel(int(text_channel_id), guild)
                        )
                        print(f"Deleted text channel {text_channel_id}")
                    except Exception as e:
                        print(f"Failed to delete text channel {text_channel_id}: {e}")
                else:
                    print("No text_channel_id found for deletion.")

            except Exception as e:
                print(f"Error during channel cleanup: {e}")

    except Exception as e:
        print(f"Error voiding game: {e}")

    finally:
        db_manager.close()
