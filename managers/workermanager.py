import logging
import asyncio
import discord
import yaml

class WorkerManager:
    def __init__(self, bot, config_path='configs/config.yml'):
        self.bot = bot
        self.config_path = config_path
        self.enabled = False
        self.tokens = []
        self.worker_bots = []  
        self.ready = asyncio.Event()
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            workers_cfg = config.get('workers', {})
            self.enabled = workers_cfg.get('enabled', False)
            self.tokens = workers_cfg.get('tokens', [])
            logging.info(f"WorkerManager config loaded: enabled={self.enabled}, tokens={len(self.tokens)}")
        except Exception as e:
            logging.error(f"Failed to load WorkerManager config: {e}")
            self.enabled = False
            self.tokens = []

    async def start_workers(self):
        if not self.enabled or not self.tokens:
            logging.info("WorkerManager is disabled or no tokens provided.")
            self.ready.set()
            return
        self.worker_bots = []
        for idx, token in enumerate(self.tokens):
            bot = discord.Client(intents=discord.Intents.all())
            self.worker_bots.append(bot)
            asyncio.create_task(self._run_worker(bot, token, idx))
        await self._wait_for_all_ready()

    async def _run_worker(self, bot, token, idx):
        @bot.event
        async def on_ready():
            logging.info(f"Worker bot #{idx+1} ready: {bot.user}")
            if all(b.is_ready() for b in self.worker_bots):
                self.ready.set()
        try:
            await bot.start(token)
        except Exception as e:
            logging.error(f"Worker bot #{idx+1} failed to start: {e}")

    async def _wait_for_all_ready(self):
        await self.ready.wait()

    async def move_players(self, moves: list):
        if not self.enabled or not self.worker_bots:
            raise RuntimeError("WorkerManager is not enabled or not initialized.")
        tasks = []
        for idx, move in enumerate(moves):
            bot = self.worker_bots[idx % len(self.worker_bots)]
            tasks.append(self._move_player(bot, move['player_id'], move['channel_id']))
        await asyncio.gather(*tasks)

    async def _move_player(self, bot, player_id, channel_id):
        try:
            guild = discord.utils.get(bot.guilds, id=int(self.bot.config['bot']['guildid']))
            member = guild.get_member(player_id) if guild else None
            channel = bot.get_channel(channel_id) if guild else None
            if member and channel:
                await member.move_to(channel)
                logging.info(f"Worker moved player {player_id} to channel {channel_id}")
            else:
                logging.warning(f"Worker could not move player {player_id} to channel {channel_id}")
        except Exception as e:
            logging.error(f"Worker failed to move player {player_id}: {e}")

    async def shutdown(self):
        for bot in self.worker_bots:
            await bot.close()
        self.worker_bots = []
        self.ready.clear()
