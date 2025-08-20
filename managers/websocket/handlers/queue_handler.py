
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Set
import discord
from ..models.messages import MessageType, MessageBuilder
from ..utils.error_handler import MessageValidationError


class QueueHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.bot = websocket_manager.bot
        self.logger = websocket_manager.logger
        self.db_manager = self.bot.database_manager
        self.queue_processor = getattr(self.bot, 'queue_processor', None)
        
        
        self._broadcast_task = None
        self._broadcast_interval = self.ws_manager.queue_broadcast_interval
        self._last_broadcast_data = {}
        
        
        self._register_handlers()
        
        self.logger.info("QueueHandler initialized successfully")
    
    def _register_handlers(self) -> None:
        self.ws_manager.register_handler(MessageType.QUEUE_FROM_INGAME, self.handle_queue_from_ingame)
        self.logger.debug("Registered queue message handlers")
    
    async def start_broadcasting(self) -> None:
        if not self.ws_manager.enabled:
            return
        
        if self._broadcast_task and not self._broadcast_task.done():
            self.logger.warning("Queue broadcasting already running")
            return
        
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        self.ws_manager._background_tasks.add(self._broadcast_task)
        self.logger.info(f"Started queue status broadcasting with {self._broadcast_interval}s interval")
    
    async def stop_broadcasting(self) -> None:
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Stopped queue status broadcasting")
    
    async def _broadcast_loop(self) -> None:
        try:
            while True:
                if not self.ws_manager.enabled or not self.ws_manager.clients:
                    await asyncio.sleep(self._broadcast_interval)
                    continue
                
                try:
                    
                    queue_data = await self.get_queue_data()
                    
                    
                    current_time = time.time()
                    should_broadcast = (
                        queue_data != self._last_broadcast_data or
                        current_time - getattr(self, '_last_broadcast_time', 0) > 10  
                    )
                    
                    if should_broadcast:
                        
                        message = MessageBuilder.build_queue_status(queue_data)
                        await self.ws_manager.broadcast(message)
                        
                        self._last_broadcast_data = queue_data
                        self._last_broadcast_time = current_time
                        
                        self.logger.debug(f"Broadcasted queue status: {len(queue_data)} queues")
                
                except Exception as e:
                    self.logger.error(f"Error in queue broadcast loop: {e}")
                
                await asyncio.sleep(self._broadcast_interval)
                
        except asyncio.CancelledError:
            self.logger.debug("Queue broadcast loop cancelled")
        except Exception as e:
            self.logger.error(f"Unexpected error in queue broadcast loop: {e}")
    
    async def get_queue_data(self) -> Dict[str, Any]:
        try:
            queues_data = {}
            
            
            queue_configs = self.db_manager.find('queues', {})
            
            for queue_config in queue_configs:
                channel_id = queue_config['channelid']
                
                try:
                    
                    channel = self.bot.get_channel(int(channel_id))
                    if not channel:
                        self.logger.debug(f"Channel {channel_id} not found, skipping")
                        continue
                    
                    
                    voice_members = [member for member in channel.members if not member.bot]
                    player_igns = []
                    
                    
                    for member in voice_members:
                        user_data = self.db_manager.find_one('users', {'discordid': str(member.id)})
                        if user_data and user_data.get('ign'):
                            player_igns.append(user_data['ign'])
                    
                    
                    elo_range = await self._calculate_elo_range(voice_members, queue_config)
                    
                    
                    queue_name = getattr(channel, 'name', f'queue_{channel_id}')
                    queues_data[queue_name] = {
                        'players': player_igns,
                        'elo_range': elo_range,
                        'capacity': queue_config.get('maxplayers', 8)
                    }
                    
                except Exception as e:
                    self.logger.error(f"Error processing queue {channel_id}: {e}")
                    continue
            
            return queues_data
            
        except Exception as e:
            self.logger.error(f"Error getting queue data: {e}")
            return {}
    
    async def _calculate_elo_range(self, members: List[discord.Member], queue_config: Dict[str, Any]) -> Dict[str, int]:
        try:
            if not members:
                return {
                    'min': queue_config.get('minelo', 0),
                    'max': queue_config.get('maxelo', 3000)
                }
            
            player_elos = []
            for member in members:
                user_data = self.db_manager.find_one('users', {'discordid': str(member.id)})
                if user_data:
                    player_elos.append(user_data.get('elo', 1000))
            
            if not player_elos:
                return {
                    'min': queue_config.get('minelo', 0),
                    'max': queue_config.get('maxelo', 3000)
                }
            
            return {
                'min': min(player_elos),
                'max': max(player_elos)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating ELO range: {e}")
            return {
                'min': queue_config.get('minelo', 0),
                'max': queue_config.get('maxelo', 3000)
            }
    
    async def handle_queue_from_ingame(self, message: Dict[str, Any], websocket) -> None:
        try:
            
            ign = message.get('ign')
            queue_type = message.get('queue_type')
            
            if not ign or not queue_type:
                await self._send_queue_error(websocket, "Missing required fields: ign or queue_type")
                return
            
            self.logger.info(f"Processing queue request from {ign} for queue type {queue_type}")
            
            
            user_data = self.db_manager.find_one('users', {'ign': ign})
            if not user_data:
                await self._send_queue_error(websocket, f"Player {ign} not found in database")
                return
            
            discord_id = int(user_data['discordid'])
            
            
            queue_channel_id = await self._find_queue_for_type(queue_type, user_data)
            if not queue_channel_id:
                await self._send_queue_error(websocket, f"No suitable queue found for type {queue_type}")
                return
            
            
            validation_result = await self._validate_queue_join(discord_id, queue_channel_id, user_data)
            if not validation_result['valid']:
                await self._send_queue_error(websocket, validation_result['reason'])
                return
            
            
            if self.queue_processor:
                try:
                    await self.queue_processor.process_queue_join(discord_id, queue_channel_id)
                    
                    
                    await self._send_queue_success(websocket, ign, queue_type, queue_channel_id)
                    self.logger.info(f"Successfully added {ign} to queue {queue_channel_id}")
                    
                except Exception as e:
                    self.logger.error(f"Error processing queue join for {ign}: {e}")
                    await self._send_queue_error(websocket, f"Failed to join queue: {str(e)}")
            else:
                await self._send_queue_error(websocket, "Queue processor not available")
                
        except Exception as e:
            self.logger.error(f"Error handling queue from ingame: {e}")
            await self._send_queue_error(websocket, f"Internal server error: {str(e)}")
    
    async def _find_queue_for_type(self, queue_type: str, user_data: Dict[str, Any]) -> Optional[str]:
        try:
            player_elo = user_data.get('elo', 1000)
            
            
            queue_configs = self.db_manager.find('queues', {})
            
            suitable_queues = []
            
            for queue_config in queue_configs:
                
                is_casual = queue_config.get('iscasual', False)
                queue_matches_type = (
                    (queue_type.lower() == 'casual' and is_casual) or
                    (queue_type.lower() == 'ranked' and not is_casual) or
                    queue_type.lower() == 'any'
                )
                
                if not queue_matches_type:
                    continue
                
                
                min_elo = queue_config.get('minelo', 0)
                max_elo = queue_config.get('maxelo', 9999)
                
                if min_elo <= player_elo <= max_elo:
                    suitable_queues.append({
                        'channel_id': queue_config['channelid'],
                        'priority': 1 if not is_casual else 2  
                    })
            
            if not suitable_queues:
                return None
            
            
            suitable_queues.sort(key=lambda x: x['priority'])
            return suitable_queues[0]['channel_id']
            
        except Exception as e:
            self.logger.error(f"Error finding queue for type {queue_type}: {e}")
            return None
    
    async def _validate_queue_join(self, discord_id: int, channel_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            
            if user_data.get('banned', False):
                ban_expiry = user_data.get('ban_expiry')
                if not ban_expiry or time.time() < ban_expiry.time:
                    return {
                        'valid': False,
                        'reason': f"Player is banned: {user_data.get('ban_reason', 'No reason provided')}"
                    }
            
            
            if self.queue_processor and hasattr(self.queue_processor, 'player_queue_map'):
                if discord_id in self.queue_processor.player_queue_map:
                    current_queue = self.queue_processor.player_queue_map[discord_id]
                    if current_queue == channel_id:
                        return {
                            'valid': False,
                            'reason': "Player is already in this queue"
                        }
                    else:
                        return {
                            'valid': False,
                            'reason': "Player is already in another queue"
                        }
            
            
            queue_config = self.db_manager.find_one('queues', {'channelid': channel_id})
            if not queue_config:
                return {
                    'valid': False,
                    'reason': f"Queue {channel_id} not found"
                }
            
            
            player_elo = user_data.get('elo', 1000)
            min_elo = queue_config.get('minelo', 0)
            max_elo = queue_config.get('maxelo', 9999)
            
            if not (min_elo <= player_elo <= max_elo):
                return {
                    'valid': False,
                    'reason': f"Player ELO {player_elo} is outside queue range {min_elo}-{max_elo}"
                }
            
            
            if self.queue_processor and hasattr(self.queue_processor, 'queues'):
                queue_state = self.queue_processor.queues.get(channel_id)
                if queue_state:
                    current_players = len(queue_state.get('players', set()))
                    max_players = queue_config.get('maxplayers', 8)
                    
                    if current_players >= max_players:
                        return {
                            'valid': False,
                            'reason': f"Queue is full ({current_players}/{max_players})"
                        }
            
            
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                guild = channel.guild
                member = guild.get_member(discord_id)
                if member and member.voice and member.voice.channel and member.voice.channel.id != int(channel_id):
                    return {
                        'valid': False,
                        'reason': "Player must be in the correct voice channel to join queue"
                    }
            
            return {'valid': True, 'reason': ''}
            
        except Exception as e:
            self.logger.error(f"Error validating queue join: {e}")
            return {
                'valid': False,
                'reason': f"Validation error: {str(e)}"
            }
    
    async def _send_queue_success(self, websocket, ign: str, queue_type: str, channel_id: str) -> None:
        try:
            response = {
                'type': 'queue_join_success',
                'ign': ign,
                'queue_type': queue_type,
                'channel_id': channel_id,
                'message': f'Successfully joined {queue_type} queue'
            }
            await self.ws_manager.send_to_client(websocket, response)
            
        except Exception as e:
            self.logger.error(f"Error sending queue success response: {e}")
    
    async def _send_queue_error(self, websocket, error_message: str) -> None:
        try:
            response = {
                'type': 'queue_join_error',
                'error': error_message
            }
            await self.ws_manager.send_to_client(websocket, response)
            
        except Exception as e:
            self.logger.error(f"Error sending queue error response: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        try:
            stats = {
                'broadcasting_active': self._broadcast_task and not self._broadcast_task.done(),
                'broadcast_interval': self._broadcast_interval,
                'last_broadcast_time': getattr(self, '_last_broadcast_time', 0),
                'queues_tracked': len(self._last_broadcast_data),
                'total_players_in_queues': sum(
                    len(queue_data.get('players', []))
                    for queue_data in self._last_broadcast_data.values()
                )
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting queue stats: {e}")
            return {}
    
    async def force_broadcast(self) -> None:
        try:
            if not self.ws_manager.enabled or not self.ws_manager.clients:
                self.logger.warning("Cannot force broadcast: WebSocket disabled or no clients")
                return
            
            queue_data = await self.get_queue_data()
            message = MessageBuilder.build_queue_status(queue_data)
            await self.ws_manager.broadcast(message)
            
            self._last_broadcast_data = queue_data
            self._last_broadcast_time = time.time()
            
            self.logger.info("Forced queue status broadcast completed")
            
        except Exception as e:
            self.logger.error(f"Error in force broadcast: {e}")
    
    async def cleanup(self) -> None:
        try:
            await self.stop_broadcasting()
            
            
            self.ws_manager.unregister_handler(MessageType.QUEUE_FROM_INGAME)
            
            self.logger.info("QueueHandler cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during QueueHandler cleanup: {e}")
