import discord
from discord.ext import commands
import logging
import sys
import yaml
import os
from managers.command_manager import CommandManager
from managers.database_manager import DatabaseManager
from managers.event_manager import EventManager
from utils.error_handler import ErrorHandler
from utils.embed_builder import EmbedBuilder
from managers.party_manager import PartyManager
from managers.ban_manager import BanManager
from managers.strikes_manager import StrikesManager
from managers.screenshare_manager import ScreenshareManager
from utils.daily_elo_reset import DailyEloReset
from utils.elo_decay import EloDecay
from managers.permission_manager import PermissionManager
from managers.mute_manager import MuteManager
from managers.websocket_manager import WebSocketManager
import asyncio
from discord.ext import tasks


class TeamVcCleanup:
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database_manager.db
        self.config = bot.config
        self.logger = bot.logger

    @tasks.loop(seconds=15)
    async def cleanup_channels(self):
        try:
            category_id = int(self.config["categories"]["gamesvoicecategory"])
            guild = self.bot.get_guild(int(self.config["bot"]["guildid"]))
            category = guild.get_channel(category_id)

            if not category:
                self.logger.error("Could not find games voice category")
                return

            for channel in category.voice_channels:
                if len(channel.members) == 0:
                    game_channel = self.db["gameschannels"].find_one(
                        {"channelid": str(channel.id)}
                    )
                    if game_channel:
                        game = self.db["games"].find_one(
                            {"_id": game_channel["gameid"]}
                        )
                        if game and (
                            game.get("scored", False) or game.get("voided", False)
                        ):
                            try:
                                await channel.delete()
                                self.logger.info(
                                    f"Deleted empty game voice channel {channel.name} for completed game {game_channel['gameid']}"
                                )

                                self.db["gameschannels"].delete_one(
                                    {"channelid": str(channel.id)}
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Error deleting voice channel {channel.id}: {e}"
                                )

        except Exception as e:
            self.logger.error(f"Error in cleanup_channels task: {e}")

    @cleanup_channels.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()


class Bot(commands.Bot):
    def __init__(self):
        import datetime

        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True

        self.config = self.load_config()

        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler("bot.log"),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger("bot")

        command_prefix = self.config.get("bot", {}).get("prefix", "!")

        super().__init__(
            command_prefix=command_prefix, intents=intents, help_command=None
        )

        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(self)
        self.command_manager = CommandManager(self)
        self.event_manager = EventManager(self)
        self.party_manager = PartyManager(
            config_file="configs/config.yml", db_manager=self.database_manager
        )
        self.ban_manager = BanManager(self)
        self.strikes_manager = StrikesManager(self)
        self.permission_manager = PermissionManager()
        self.mute_manager = MuteManager(self)
        self.screenshare_manager = ScreenshareManager(self)
        self.websocket_manager = WebSocketManager(self, self.config)

        self.worker_manager = None
        self.queue_processor = None

        self.uptime = datetime.datetime.utcnow()

        self._setup_signal_handlers()

    def load_token(self) -> str:
        config_path = os.path.join("configs", "config.yml")
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                return config["bot"]["bottoken"]
        except Exception as e:
            self.logger.error(f"Failed to load bot token: {e}")
            raise

    def load_config(self) -> dict:
        config_path = os.path.join("configs", "config.yml")
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                return yaml.safe_load(file)
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise

    async def setup_hook(self):
        self.logger.info("Initializing bot systems...")

        from managers.workermanager import WorkerManager

        self.worker_manager = WorkerManager(self)
        if self.worker_manager.enabled:
            await self.worker_manager.start_workers()
            self.logger.info("Worker system: ✓")

        self.command_manager.load_permissions()
        await self.command_manager.load_commands()
        await self.event_manager.setup_events()
        self.logger.info("Core systems loaded: ✓")

        try:
            from events.messagenuker import MessageNuker
            from events.voicechannelnuker import VoiceChannelNuker

            await self.add_cog(MessageNuker(self))
            await self.add_cog(VoiceChannelNuker(self))
            self.logger.info("Event handlers: ✓")
        except Exception as e:
            self.logger.error(f"Failed to load event handlers: {e}")

        await self.ban_manager.start_auto_unban()
        print("Auto-unban system initialized.")

        await self.mute_manager.start_auto_unmute()
        print("Auto-unmute system initialized.")

        await self.strikes_manager.start_strikes_checker()
        print("Auto-remove strikes system initialized.")

        self.logger.info("Starting automatic tasks...")

        await self.party_manager.check_inactive_parties()
        self.loop.create_task(self.auto_party_disband_task())

        daily_elo_reset = DailyEloReset(self.database_manager)
        self.loop.create_task(daily_elo_reset.reset_daily_elo_task())

        elo_decay = EloDecay(
            self.database_manager, self.config, self, self.embed_builder
        )
        self.loop.create_task(elo_decay.elo_decay_task())

        from managers.queue_processor import QueueProcessor

        self.queue_processor = QueueProcessor(self)

        if self.websocket_manager.is_enabled():
            await self.websocket_manager.start()
            self.logger.info("WebSocket system: ✓")
        else:
            self.logger.info("WebSocket system: Disabled")

        self.cleanup_task = TeamVcCleanup(self)
        self.cleanup_task.cleanup_channels.start()

        self.logger.info("All systems initialized successfully.")

    async def on_ready(self):
        self.logger.info("Zzzzzzzzz All systems are online!")

        self.status_messages = [
            {"type": "playing", "name": "=register"},
            {"type": "playing", "name": self.config["server"]["servername"]},
            {"type": "playing", "name": self.config["server"]["serverip"]},
            {"type": "playing", "name": "Made by @deyoyk"},
        ]
        self.current_status_index = 0
        self.rotate_status_task = self.loop.create_task(self.rotate_status())

        try:
            channel_id = int(self.config.get("logging", {}).get("startup"))
            channel = self.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Bot Started",
                    description=f"Bot is now online!\nUser: {self.user} ({self.user.id})",
                    color=discord.Color.green(),
                )
                await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send startup embed: {e}")

    async def rotate_status(self):
        try:
            while not self.is_closed():
                message = self.status_messages[self.current_status_index]
                activity_type = message.get("type", "playing").lower()
                activity_name = message.get("name", "Ranked Bedwars")
                status = self.config.get("botstatus", "online").lower()

                match activity_type:
                    case "playing":
                        activity = discord.Game(name=activity_name)
                    case "streaming":
                        activity = discord.Streaming(
                            name=activity_name, url="http://twitch.tv/streamer"
                        )
                    case "listening":
                        activity = discord.Activity(
                            type=discord.ActivityType.listening, name=activity_name
                        )
                    case "watching":
                        activity = discord.Activity(
                            type=discord.ActivityType.watching, name=activity_name
                        )
                    case _:
                        activity = discord.Game(name=activity_name)

                await self.change_presence(
                    activity=activity,
                    status=getattr(discord.Status, status, discord.Status.online),
                )

                self.current_status_index = (self.current_status_index + 1) % len(
                    self.status_messages
                )

                await asyncio.sleep(10)
        except Exception as e:
            self.logger.error(f"Error in status rotation task: {e}")

    async def auto_party_disband_task(self):
        while True:
            try:
                await self.party_manager.check_inactive_parties()
            except Exception as e:
                self.logger.error(f"Error in auto party disband task: {e}")
            await asyncio.sleep(600)

    def _setup_signal_handlers(self):
        try:
            import signal

            def handle_exit(signum, frame):
                print(f"Received signal {signum}, initiating clean shutdown...")
                self.loop.create_task(self.close())

            signal.signal(signal.SIGINT, handle_exit)
            signal.signal(signal.SIGTERM, handle_exit)

            self.logger.info("Signal handlers for graceful shutdown registered")
        except Exception as e:
            self.logger.error(f"Failed to set up signal handlers: {e}")

    async def close(self):
        self.logger.info("Bot shutdown initiated, cleaning up resources...")

        try:
            channel_id = int(self.config.get("logging", {}).get("startup"))
            channel = self.get_channel(channel_id)
            if channel:
                embed = discord.Embed(
                    title="Bot Shutdown",
                    description=f"Bot is shutting down.\nUser: {self.user} ({self.user.id})",
                    color=discord.Color.red(),
                )
                await channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to send shutdown embed: {e}")

        if self.queue_processor:
            self.logger.info("Cleaning up queue processor...")
            try:
                await self.queue_processor.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up queue processor: {e}")

        if self.websocket_manager and self.websocket_manager.is_enabled():
            self.logger.info("Cleaning up WebSocket manager...")
            try:
                await self.websocket_manager.stop()
            except Exception as e:
                self.logger.error(f"Error cleaning up WebSocket manager: {e}")

        if hasattr(self, "cleanup_task"):
            self.logger.info("Stopping TeamVcCleanup task...")
            try:
                self.cleanup_task.cleanup_channels.cancel()
            except Exception as e:
                self.logger.error(f"Error stopping TeamVcCleanup task: {e}")

        await super().close()
        self.logger.info("Bot shutdown complete")


def main():
    bot = Bot()

    try:
        bot.run(bot.config["bot"]["bottoken"])
    except discord.LoginFailure:
        bot.logger.error("Invalid token provided. Please check your bot token.")
    except Exception as e:
        bot.logger.error(f"An error occurred during bot startup: {e}")


if __name__ == "__main__":
    main()
