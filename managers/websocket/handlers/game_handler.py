
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from ..models.messages import MessageType, MessageBuilder
from ..utils.error_handler import WebSocketErrorHandler


class GameHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.bot = websocket_manager.bot
        self.logger = websocket_manager.logger
        self.config = websocket_manager.config
        
        
        self.max_retry_attempts = websocket_manager.max_retry_attempts
        self.warp_timeout = websocket_manager.timeout
        
        
        self.warp_timeouts: Dict[str, asyncio.Task] = {}
        self.warp_attempts: Dict[str, int] = {}
        self.team_data: Dict[str, Dict[str, Any]] = {}
        self.pending_warps: Dict[str, Dict[str, Any]] = {}
        
        
        self._register_handlers()
        
        self.logger.info("GameHandler initialized successfully")
    
    def _register_handlers(self):
        self.ws_manager.register_handler(MessageType.WARP_SUCCESS, self.handle_warp_success)
        self.ws_manager.register_handler(MessageType.WARP_FAILED_ARENA, self.handle_warp_failed_arena)
        self.ws_manager.register_handler(MessageType.WARP_FAILED_OFFLINE, self.handle_warp_failed_offline)
        self.ws_manager.register_handler(MessageType.RETRY_GAME, self.handle_retry_game)
        self.ws_manager.register_handler(MessageType.AUTO_RETRY_FROM_INGAME, self.handle_auto_retry_from_ingame)
        
        self.logger.debug("GameHandler message handlers registered")
    
    async def warp_players(
        self, 
        game_id: str, 
        map_name: str, 
        is_ranked: bool, 
        team1: List[Dict[str, str]], 
        team2: List[Dict[str, str]]
    ) -> bool:
        try:
            self.logger.info(f"Starting warp for game {game_id} on map {map_name}")
            
            
            self.team_data[game_id] = {
                'map_name': map_name,
                'is_ranked': is_ranked,
                'team1': team1,
                'team2': team2,
                'original_request_time': asyncio.get_event_loop().time()
            }
            
            
            self.warp_attempts[game_id] = 1
            
            
            warp_message = MessageBuilder.build_warp_players(
                game_id=game_id,
                map_name=map_name,
                is_ranked=is_ranked,
                team1=team1,
                team2=team2
            )
            
            
            self.pending_warps[game_id] = {
                'message': warp_message,
                'start_time': asyncio.get_event_loop().time(),
                'team1_igns': [player['ign'] for player in team1],
                'team2_igns': [player['ign'] for player in team2]
            }
            
            
            try:
                response = await self.ws_manager.send_request_with_response(
                    message_type=MessageType.WARP_PLAYERS,
                    message_data={
                        'game_id': game_id,
                        'map': map_name,
                        'is_ranked': is_ranked,
                        'team1': team1,
                        'team2': team2
                    },
                    timeout=self.warp_timeout
                )
                
                
                self.logger.info(f"Warp successful for game {game_id}")
                await self._handle_successful_warp(game_id)
                return True
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Warp request timed out for game {game_id}")
                await self._handle_warp_timeout(game_id)
                raise Exception(f"Warp request timed out for game {game_id}")
                
            except Exception as e:
                self.logger.error(f"Warp request failed for game {game_id}: {e}")
                await self._cleanup_warp_data(game_id)
                raise e
                
        except Exception as e:
            self.logger.error(f"Error in warp_players for game {game_id}: {e}")
            await self._cleanup_warp_data(game_id)
            raise e
    
    async def handle_warp_success(self, message: Dict[str, Any], websocket) -> None:
        try:
            game_id = message.get('game_id')
            if not game_id:
                self.logger.error("Warp success message missing game_id")
                return
            
            self.logger.info(f"Received warp success for game {game_id}")
            
            
            await self._handle_successful_warp(game_id)
            
        except Exception as e:
            self.logger.error(f"Error handling warp success: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_warp_failed_arena(self, message: Dict[str, Any], websocket) -> None:
        try:
            game_id = message.get('game_id')
            map_name = message.get('map')
            
            if not game_id:
                self.logger.error("Warp failed arena message missing game_id")
                return
            
            self.logger.warning(f"Warp failed for game {game_id}: Arena '{map_name}' not found")
            
            
            await self._handle_warp_failure(
                game_id, 
                f"Arena '{map_name}' not found", 
                retry_eligible=False  
            )
            
        except Exception as e:
            self.logger.error(f"Error handling warp failed arena: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_warp_failed_offline(self, message: Dict[str, Any], websocket) -> None:
        try:
            game_id = message.get('game_id')
            offline_players = message.get('offline_players', [])
            
            if not game_id:
                self.logger.error("Warp failed offline message missing game_id")
                return
            
            offline_list = ', '.join(offline_players) if offline_players else 'unknown players'
            self.logger.warning(f"Warp failed for game {game_id}: Offline players - {offline_list}")
            
            
            await self._handle_warp_failure(
                game_id, 
                f"Players offline: {offline_list}", 
                retry_eligible=True
            )
            
        except Exception as e:
            self.logger.error(f"Error handling warp failed offline: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_retry_game(self, message: Dict[str, Any], websocket) -> None:
        try:
            game_id = message.get('game_id')
            
            if not game_id:
                self.logger.error("Retry game message missing game_id")
                return
            
            self.logger.info(f"Received retry request for game {game_id}")
            
            
            success = await self._retry_warp(game_id)
            
            if success:
                self.logger.info(f"Game {game_id} retry initiated successfully")
            else:
                self.logger.warning(f"Game {game_id} retry failed or not eligible")
            
        except Exception as e:
            self.logger.error(f"Error handling retry game: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)

    async def handle_auto_retry_from_ingame(self, message: Dict[str, Any], websocket) -> None:
        try:
            game_id = message.get('game_id') or message.get('gameid')
            if not game_id:
                self.logger.error("Auto-retry message missing game_id/gameid")
                return
            self.logger.info(f"Received auto-retry-from-ingame for game {game_id}")

            await self._notify_autoretry(game_id)
        except Exception as e:
            self.logger.error(f"Error handling auto-retry-from-ingame: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def _handle_successful_warp(self, game_id: str) -> None:
        try:
            self.logger.info(f"Processing successful warp for game {game_id}")
            
            
            await self._cancel_warp_timeout(game_id)
            
            
            pending_warp = self.pending_warps.get(game_id, {})
            team_data = self.team_data.get(game_id, {})
            
            
            
            await self._notify_game_started(game_id, team_data, pending_warp)
            
            
            await self._cleanup_warp_data(game_id)
            
            self.logger.info(f"Successfully processed warp completion for game {game_id}")
            
        except Exception as e:
            self.logger.error(f"Error handling successful warp for game {game_id}: {e}")
    
    async def _handle_warp_failure(self, game_id: str, reason: str, retry_eligible: bool = True) -> None:
        try:
            self.logger.warning(f"Processing warp failure for game {game_id}: {reason}")
            
            
            await self._cancel_warp_timeout(game_id)
            
            
            current_attempts = self.warp_attempts.get(game_id, 0)
            
            if retry_eligible and current_attempts < self.max_retry_attempts:
                self.logger.info(f"Attempting retry for game {game_id} (attempt {current_attempts + 1}/{self.max_retry_attempts})")
                
                
                await asyncio.sleep(5.0)
                
                
                retry_success = await self._retry_warp(game_id)
                
                if not retry_success:
                    
                    await self._handle_final_warp_failure(game_id, f"{reason} (retry failed)")
            else:
                
                if not retry_eligible:
                    await self._handle_final_warp_failure(game_id, f"{reason} (not retryable)")
                else:
                    await self._handle_final_warp_failure(game_id, f"{reason} (max retries exceeded)")
            
        except Exception as e:
            self.logger.error(f"Error handling warp failure for game {game_id}: {e}")
            await self._handle_final_warp_failure(game_id, f"Error processing failure: {e}")
    
    async def _handle_final_warp_failure(self, game_id: str, reason: str) -> None:
        try:
            self.logger.error(f"Final warp failure for game {game_id}: {reason}")
            
            
            team_data = self.team_data.get(game_id, {})
            pending_warp = self.pending_warps.get(game_id, {})
            
            
            await self._notify_game_failed(game_id, reason, team_data, pending_warp)
            
            
            await self._cleanup_warp_data(game_id)
            
        except Exception as e:
            self.logger.error(f"Error handling final warp failure for game {game_id}: {e}")
    
    async def _retry_warp(self, game_id: str) -> bool:
        try:
            
            team_data = self.team_data.get(game_id)
            if not team_data:
                self.logger.warning(f"No team data found for game {game_id} retry")
                return False
            
            
            current_attempts = self.warp_attempts.get(game_id, 0)
            if current_attempts >= self.max_retry_attempts:
                self.logger.warning(f"Max retry attempts reached for game {game_id}")
                return False
            
            
            self.warp_attempts[game_id] = current_attempts + 1
            
            self.logger.info(f"Retrying warp for game {game_id} (attempt {self.warp_attempts[game_id]})")
            
            
            warp_message = MessageBuilder.build_warp_players(
                game_id=game_id,
                map_name=team_data['map_name'],
                is_ranked=team_data['is_ranked'],
                team1=team_data['team1'],
                team2=team_data['team2']
            )
            
            
            self.pending_warps[game_id] = {
                'message': warp_message,
                'start_time': asyncio.get_event_loop().time(),
                'team1_igns': [player['ign'] for player in team_data['team1']],
                'team2_igns': [player['ign'] for player in team_data['team2']],
                'retry_attempt': self.warp_attempts[game_id]
            }
            
            
            try:
                response = await self.ws_manager.send_request_with_response(
                    message_type=MessageType.WARP_PLAYERS,
                    message_data={
                        'game_id': game_id,
                        'map': team_data['map_name'],
                        'is_ranked': team_data['is_ranked'],
                        'team1': team_data['team1'],
                        'team2': team_data['team2']
                    },
                    timeout=self.warp_timeout
                )
                
                
                self.logger.info(f"Retry successful for game {game_id}")
                await self._handle_successful_warp(game_id)
                return True
                
            except asyncio.TimeoutError:
                self.logger.warning(f"Retry request timed out for game {game_id}")
                return False
                
            except Exception as e:
                self.logger.error(f"Retry request failed for game {game_id}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in retry_warp for game {game_id}: {e}")
            return False
    
    async def _handle_warp_timeout(self, game_id: str) -> None:
        try:
            self.logger.warning(f"Warp timeout for game {game_id}")
            
            
            await self._handle_warp_failure(game_id, "Warp request timed out", retry_eligible=True)
            
        except Exception as e:
            self.logger.error(f"Error handling warp timeout for game {game_id}: {e}")
    
    async def _cancel_warp_timeout(self, game_id: str) -> None:
        timeout_task = self.warp_timeouts.get(game_id)
        if timeout_task and not timeout_task.done():
            timeout_task.cancel()
            try:
                await timeout_task
            except asyncio.CancelledError:
                pass
        
        self.warp_timeouts.pop(game_id, None)
    
    async def _cleanup_warp_data(self, game_id: str) -> None:
        try:
            
            await self._cancel_warp_timeout(game_id)
            
            
            self.warp_attempts.pop(game_id, None)
            self.team_data.pop(game_id, None)
            self.pending_warps.pop(game_id, None)
            
            self.logger.debug(f"Cleaned up warp data for game {game_id}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up warp data for game {game_id}: {e}")
    
    async def _notify_game_started(self, game_id: str, team_data: Dict[str, Any], pending_warp: Dict[str, Any]) -> None:
        try:
            
            
            
            team1_igns = [player['ign'] for player in team_data.get('team1', [])]
            team2_igns = [player['ign'] for player in team_data.get('team2', [])]
            
            self.logger.info(
                f"Game {game_id} started successfully on map {team_data.get('map_name', 'unknown')} "
                f"- Team1: {', '.join(team1_igns)} vs Team2: {', '.join(team2_igns)}"
            )
            
            
            
            
            
            
            
            
        except Exception as e:
            self.logger.error(f"Error notifying game started for {game_id}: {e}")

    async def _notify_autoretry(self, game_id: str) -> None:
        try:
            # Resolve text channel for the game and send a message
            db = self.bot.database_manager
            game_channel = db.find_one('gameschannels', {'gameid': game_id})
            if not game_channel:
                self.logger.debug(f"No gameschannels record for {game_id}")
                return
            text_channel_id = game_channel.get('textchannelid')
            if not text_channel_id:
                self.logger.debug(f"No textchannelid for game {game_id}")
                return
            text_channel = self.bot.get_channel(int(text_channel_id))
            if not text_channel:
                self.logger.debug(f"Text channel not found for id {text_channel_id}")
                return

            await text_channel.send(f"🔁 Retrying game `{game_id}`... Please wait while we re-warp players.")
        except Exception as e:
            self.logger.error(f"Failed to notify auto-retry for {game_id}: {e}")
    
    async def _notify_game_failed(self, game_id: str, reason: str, team_data: Dict[str, Any], pending_warp: Dict[str, Any]) -> None:
        try:
            
            
            
            team1_igns = [player['ign'] for player in team_data.get('team1', [])]
            team2_igns = [player['ign'] for player in team_data.get('team2', [])]
            
            self.logger.error(
                f"Game {game_id} failed to start: {reason} "
                f"- Team1: {', '.join(team1_igns)} vs Team2: {', '.join(team2_igns)}"
            )
            
            
            
            
            
            
            
            
        except Exception as e:
            self.logger.error(f"Error notifying game failed for {game_id}: {e}")
    
    def get_warp_stats(self) -> Dict[str, Any]:
        return {
            'pending_warps': len(self.pending_warps),
            'active_timeouts': len(self.warp_timeouts),
            'games_with_attempts': len(self.warp_attempts),
            'stored_team_data': len(self.team_data),
            'max_retry_attempts': self.max_retry_attempts,
            'warp_timeout': self.warp_timeout
        }
    
    def get_game_info(self, game_id: str) -> Optional[Dict[str, Any]]:
        if game_id not in self.pending_warps and game_id not in self.team_data:
            return None
        
        info = {
            'game_id': game_id,
            'attempts': self.warp_attempts.get(game_id, 0),
            'has_timeout': game_id in self.warp_timeouts,
            'has_team_data': game_id in self.team_data,
            'has_pending_warp': game_id in self.pending_warps
        }
        
        
        if game_id in self.team_data:
            team_data = self.team_data[game_id]
            info.update({
                'map_name': team_data.get('map_name'),
                'is_ranked': team_data.get('is_ranked'),
                'team1_count': len(team_data.get('team1', [])),
                'team2_count': len(team_data.get('team2', [])),
                'original_request_time': team_data.get('original_request_time')
            })
        
        
        if game_id in self.pending_warps:
            pending = self.pending_warps[game_id]
            info.update({
                'warp_start_time': pending.get('start_time'),
                'retry_attempt': pending.get('retry_attempt', 1)
            })
        
        return info
    
    async def cancel_warp(self, game_id: str) -> bool:
        try:
            if game_id not in self.pending_warps and game_id not in self.team_data:
                return False
            
            self.logger.info(f"Cancelling warp for game {game_id}")
            
            
            await self._cleanup_warp_data(game_id)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling warp for game {game_id}: {e}")
            return False
    
    async def cleanup(self) -> None:
        try:
            self.logger.info("Cleaning up GameHandler...")
            
            
            for game_id in list(self.warp_timeouts.keys()):
                await self._cancel_warp_timeout(game_id)
            
            
            self.warp_attempts.clear()
            self.team_data.clear()
            self.pending_warps.clear()
            
            self.logger.info("GameHandler cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during GameHandler cleanup: {e}")
