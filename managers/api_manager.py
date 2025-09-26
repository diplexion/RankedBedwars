import asyncio
import logging
import json
from typing import List, Optional, Dict, Any
from aiohttp import web, WSMsgType
from aiohttp.web import Request, Response
from managers.database_manager import DatabaseManager


class Player:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def to_dict(self):
        return {
            'discord_id': getattr(self, 'discord_id', ''),
            'ign': getattr(self, 'ign', ''),
            'elo': getattr(self, 'elo', 0),
            'wins': getattr(self, 'wins', 0),
            'losses': getattr(self, 'losses', 0),
            'games_played': getattr(self, 'games_played', 0),
            'win_streak': getattr(self, 'win_streak', 0),
            'highest_elo': getattr(self, 'highest_elo', 0),
            'highest_win_streak': getattr(self, 'highest_win_streak', 0),
            'beds_broken': getattr(self, 'beds_broken', 0),
            'mvps': getattr(self, 'mvps', 0),
            'final_kills': getattr(self, 'final_kills', 0),
            'kills': getattr(self, 'kills', 0),
            'deaths': getattr(self, 'deaths', 0),
            'diamonds': getattr(self, 'diamonds', 0),
            'irons': getattr(self, 'irons', 0),
            'gold': getattr(self, 'gold', 0),
            'emeralds': getattr(self, 'emeralds', 0),
            'blocks_placed': getattr(self, 'blocks_placed', 0),
            'mvp_rate': getattr(self, 'mvp_rate', 0.0),
            'win_rate': getattr(self, 'win_rate', 0.0),
            'kd_ratio': getattr(self, 'kd_ratio', 0.0)
        }


async def get_player_data(discord_id: str) -> Optional[Player]:
    try:
        db_manager = DatabaseManager()
        user = db_manager.find_one('users', {'discordid': str(discord_id)})
        
        if not user:
            return None
        
        games_played = user.get('gamesplayed', 0)
        wins = user.get('wins', 0)
        losses = user.get('losses', 0)
        mvps = user.get('mvps', 0)
        kills = user.get('kills', 0)
        deaths = user.get('deaths', 0)
        
        mvp_rate = (mvps / games_played * 100) if games_played > 0 else 0
        win_rate = (wins / games_played * 100) if games_played > 0 else 0
        kd_ratio = (kills / deaths) if deaths > 0 else kills
        
        return Player(
            discord_id=user.get('discordid', ''),
            ign=user.get('ign', ''),
            elo=user.get('elo', 0),
            wins=wins,
            losses=losses,
            games_played=games_played,
            win_streak=user.get('winstreak', 0),
            highest_elo=user.get('highest_elo', 0),
            highest_win_streak=user.get('highstwinstreak', 0),
            beds_broken=user.get('bedsbroken', 0),
            mvps=mvps,
            final_kills=user.get('finalkills', 0),
            kills=kills,
            deaths=deaths,
            diamonds=user.get('diamonds', 0),
            irons=user.get('irons', 0),
            gold=user.get('gold', 0),
            emeralds=user.get('emeralds', 0),
            blocks_placed=user.get('blocksplaced', 0),
            mvp_rate=round(mvp_rate, 2),
            win_rate=round(win_rate, 2),
            kd_ratio=round(kd_ratio, 2)
        )
    except Exception as e:
        logging.error(f"Error fetching player {discord_id}: {e}")
        return None


async def get_leaderboard_data(mode: Optional[str] = None, page: int = 1, limit: int = 10):
    try:
        db_manager = DatabaseManager()
        
        # Interpret mode as the stat field to sort by. Default to ELO when not provided
        # Supported fields are keys present in users documents
        field_aliases = {
            'elo': 'elo',
            'wins': 'wins',
            'losses': 'losses',
            'games': 'gamesplayed',
            'gamesplayed': 'gamesplayed',
            'winstreak': 'winstreak',
            'highest_elo': 'highest_elo',
            'highestelo': 'highest_elo',
            'highest_win_streak': 'highstwinstreak',
            'highstwinstreak': 'highstwinstreak',
            'beds': 'bedsbroken',
            'bedsbroken': 'bedsbroken',
            'mvps': 'mvps',
            'finalkills': 'finalkills',
            'kills': 'kills',
            'deaths': 'deaths',
            'diamonds': 'diamonds',
            'irons': 'irons',
            'gold': 'gold',
            'emeralds': 'emeralds',
            'blocks': 'blocksplaced',
            'blocksplaced': 'blocksplaced',
            'dailyelo': 'dailyelo'
        }
        sort_field = 'elo'
        if mode is not None and str(mode).strip() != '':
            key = str(mode).lower().strip()
            if key not in field_aliases:
                raise ValueError(
                    f"Invalid mode/stat. Use one of: {sorted(list(field_aliases.keys()))} or omit for 'elo'"
                )
            sort_field = field_aliases[key]
        
        query = {}
        
        total_players = db_manager.db['users'].count_documents(query)
        total_pages = (total_players + limit - 1) // limit
        
        if page < 1 or page > total_pages:
            page = 1
        
        skip = (page - 1) * limit
        
        players_cursor = db_manager.db['users'].find(
            query,
            {
                'discordid': 1, 'ign': 1, 'elo': 1, 'wins': 1, 'losses': 1,
                'gamesplayed': 1, 'winstreak': 1, 'highest_elo': 1,
                'highstwinstreak': 1, 'bedsbroken': 1, 'mvps': 1,
                'finalkills': 1, 'kills': 1, 'deaths': 1, 'diamonds': 1,
                'irons': 1, 'gold': 1, 'emeralds': 1, 'blocksplaced': 1, 'dailyelo': 1
            }
        ).sort(sort_field, -1).skip(skip).limit(limit)
        
        players = list(players_cursor)
        
        leaderboard_entries = []
        for i, player in enumerate(players):
            rank = skip + i + 1
            entry = {
                'rank': rank,
                'discord_id': player.get('discordid', ''),
                'ign': player.get('ign', '')
            }
            entry[sort_field] = player.get(sort_field, 0)
            leaderboard_entries.append(entry)
        
        return {
            'mode': sort_field,
            'page': page,
            'total_pages': total_pages,
            'players': leaderboard_entries
        }
        
    except Exception as e:
        logging.error(f"Error fetching leaderboard: {e}")
        raise


class APIManager:
    def __init__(self, bot, config: dict):
        self.bot = bot
        self.config = config
        self.logger = bot.logger
        
        api_config = config.get('api', {})
        self.enabled = api_config.get('enabled', True)
        self.path = api_config.get('path', '/rbw/api')
        
        self.logger.info(f"API Manager initialized - Enabled: {self.enabled}")
        if self.enabled:
            self.logger.info(f"API will be available at {self.path}")
    
    def create_routes(self, app: web.Application) -> None:
        """Add API routes to the aiohttp application"""
        if not self.enabled:
            return
        
        async def cors_handler(request, handler):
            response = await handler(request)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            return response
        
        app.middlewares.append(cors_handler)
        
        async def health_check(request):
            return web.json_response({
                "status": "healthy", 
                "service": "Ranked Bedwars API"
            })
        
        app.router.add_get(f"{self.path}/health", health_check)
        
        async def get_player_rest(request):
            discord_id = request.match_info['discord_id']
            player = await get_player_data(discord_id)
            if not player:
                return web.json_response(
                    {"error": "Player not found"}, 
                    status=404
                )
            return web.json_response(player.to_dict())
        
        async def get_leaderboard_rest(request):
            mode = request.match_info['mode']
            page = int(request.query.get('page', 1))
            limit = int(request.query.get('limit', 10))
            
            try:
                leaderboard = await get_leaderboard_data(mode, page, limit)
                return web.json_response(leaderboard)
            except Exception as e:
                return web.json_response(
                    {"error": str(e)}, 
                    status=500
                )
        
        app.router.add_get(f"{self.path}/player/{{discord_id}}", get_player_rest)
        app.router.add_get(f"{self.path}/leaderboard/{{mode}}", get_leaderboard_rest)
        
        self.logger.info(f"API routes registered at {self.path}")
    
    def is_enabled(self) -> bool:
        return self.enabled
    
    def get_status(self) -> dict:
        return {
            'enabled': self.enabled,
            'path': self.path
        }
