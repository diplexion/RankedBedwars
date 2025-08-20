import discord
from typing import Dict, Optional, Tuple, Any
import asyncio
from datetime import datetime, timedelta
from bson import Timestamp
import random
import logging
import os
import yaml

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScreenshareState:
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
class ScreenshareManager:
    def __init__(self, bot):
        self.bot = bot
        self.active_screenshares: Dict[str, dict] = {}
        self.db = bot.database_manager
        self._lock = asyncio.Lock()
        
        
        self.config = self.load_config()
        self.websocket_enabled = self.config.get('websocket', {}).get('enabled', False)
        self.ws_manager = getattr(bot, 'websocket_manager', None) if self.websocket_enabled else None
        
        
        self._load_active_screenshares()
        
        logger.info(f'ScreenshareManager initialized (WebSocket enabled: {self.websocket_enabled})')
        
    def load_config(self) -> Dict[str, Any]:
        config_path = os.path.join('configs', 'config.yml')
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}

    def _load_active_screenshares(self) -> None:
        try:
            active_ss = self.db.find('screenshares', {
                'state': {'$in': [ScreenshareState.PENDING, ScreenshareState.IN_PROGRESS]}
            })
            if active_ss:
                for ss in active_ss:
                    self.active_screenshares[ss['target_id']] = ss
            logger.info(f'Loaded {len(self.active_screenshares)} active screenshares')
        except Exception as e:
            logger.error(f'Error loading active screenshares: {e}')
            
    async def check_player_online(self, ign: str) -> bool:
        if not self.websocket_enabled or not self.ws_manager:
            
            logger.debug(f"WebSocket not enabled, assuming player {ign} is online")
            return True
            
        try:
            
            player_handler = getattr(self.ws_manager, 'player_handler', None)
            if player_handler:
                
                is_online = await asyncio.wait_for(
                    player_handler.check_player_online(ign), 
                    timeout=5.0  
                )
                logger.info(f"WebSocket player check for {ign}: {'online' if is_online else 'offline'}")
                return is_online
            else:
                logger.warning("WebSocket player_handler not available, assuming player is online")
                return True
        except asyncio.TimeoutError:
            logger.warning(f"WebSocket player check timed out for {ign}, assuming player is offline")
            return False
        except Exception as e:
            logger.error(f"Error checking player online status: {e}")
            return False  
            
    async def notify_player_screenshare(self, ign: str, screenshare_id: str, reason: str) -> bool:
        if not self.websocket_enabled or not self.ws_manager:
            logger.debug(f"WebSocket not enabled, can't notify player {ign}")
            return False
            
        try:
            
            notification_message = {
                'type': 'screenshare_notification',
                'ign': ign,
                'screenshare_id': screenshare_id,
                'reason': reason,
                'message': f"You have been selected for a screenshare. Reason: {reason}. Please join Discord immediately."
            }
            
            
            if hasattr(self.ws_manager, 'broadcast'):
                await self.ws_manager.broadcast(notification_message)
                logger.info(f"Sent screenshare notification to {ign} for screenshare {screenshare_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error sending screenshare notification to {ign}: {e}")
            return False

    async def create_screenshare(self, target_id: str, requester_id: str, reason: str, image_url: str) -> Tuple[bool, str]:
        async with self._lock:
            try:
                
                if target_id in self.active_screenshares:
                    return False, "User already has an active screenshare"

                
                player_data = self.db.find_one('users', {'discordid': str(target_id)})
                if not player_data or not player_data.get('ign'):
                    return False, "Could not find player's IGN in database"
                
                player_ign = player_data.get('ign')
                
                
                if self.websocket_enabled and self.ws_manager:
                    is_online = await self.check_player_online(player_ign)
                    if not is_online:
                        return False, f"Player {player_ign} is not currently online in-game"
                
                unique_id = await self._generate_unique_id()
                
                
                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                screenshare_data = {
                    'id': unique_id,
                    'target_id': str(target_id),
                    'requester_id': str(requester_id),
                    'screensharer_id': '',
                    'reason': reason,
                    'evidence_url': image_url,
                    'start_time': current_time,
                    'state': ScreenshareState.PENDING,
                    'close_reason': '',
                    'channel_id': '',
                    'is_frozen': False,
                    'created_at': current_time,
                    'updated_at': current_time
                }

                
                self.db.insert('screenshares', screenshare_data)
                self.active_screenshares[target_id] = screenshare_data
                logger.info(f'Created screenshare {unique_id} for user {target_id}')
                
                
                if self.websocket_enabled and self.ws_manager:
                    notification_sent = await self.notify_player_screenshare(
                        player_ign, unique_id, reason
                    )
                    if notification_sent:
                        logger.info(f"In-game notification sent to {player_ign} for screenshare {unique_id}")
                    else:
                        logger.warning(f"Failed to send in-game notification to {player_ign} for screenshare {unique_id}")
                
                return True, unique_id

            except Exception as e:
                logger.error(f'Error creating screenshare: {e}')
                return False, f"Failed to create screenshare: {str(e)}"

    async def _generate_unique_id(self, max_attempts: int = 5) -> str:
        for _ in range(max_attempts):
            unique_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=12))
            if not self.db.find_one('screenshares', {'id': unique_id}):
                return unique_id
        raise Exception("Failed to generate unique screenshare ID")

    async def update_channel_id(self, target_id: str, channel_id: str) -> Tuple[bool, str]:
        async with self._lock:
            try:
                if target_id not in self.active_screenshares:
                    return False, "No active screenshare found"

                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                update_result = self.db.update_one(
                    'screenshares',
                    {'target_id': str(target_id)},
                    {'$set': {
                        'channel_id': channel_id,
                        'updated_at': current_time
                    }}
                )

                if update_result:
                    self.active_screenshares[target_id]['channel_id'] = channel_id
                    self.active_screenshares[target_id]['updated_at'] = current_time
                    logger.info(f'Updated channel ID for screenshare {target_id}')
                    return True, "Channel updated successfully"
                return False, "Failed to update channel in database"

            except Exception as e:
                logger.error(f'Error updating channel ID: {e}')
                return False, f"Error updating channel: {str(e)}"

    async def assign_screensharer(self, target_id: str, screensharer_id: str) -> Tuple[bool, str]:
        async with self._lock:
            try:
                if target_id not in self.active_screenshares:
                    return False, "No active screenshare found"

                ss_info = self.active_screenshares[target_id]
                if ss_info['state'] != ScreenshareState.PENDING:
                    return False, f"Screenshare is in {ss_info['state']} state"

                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                
                
                self.db.increment(
                    'users',
                    {'discordid': str(screensharer_id)},
                    {'$inc': {'ss_count': 1}}
                )

                
                update_result = self.db.update_one(
                    'screenshares',
                    {'target_id': str(target_id), 'state': ScreenshareState.PENDING},
                    {'$set': {
                        'screensharer_id': screensharer_id,
                        'state': ScreenshareState.IN_PROGRESS,
                        'is_frozen': True,
                        'updated_at': current_time
                    }}
                )

                if update_result:
                    self.active_screenshares[target_id].update({
                        'screensharer_id': screensharer_id,
                        'state': ScreenshareState.IN_PROGRESS,
                        'is_frozen': True,
                        'updated_at': current_time
                    })
                    
                    
                    if self.websocket_enabled and self.ws_manager:
                        player_data = self.db.find_one('users', {'discordid': str(target_id)})
                        if player_data and player_data.get('ign'):
                            player_ign = player_data.get('ign')
                            
                            notification_message = f"Staff member has been assigned to your screenshare. Please join the Discord voice channel immediately."
                            await self.ws_manager.send_player_notification(player_ign, notification_message)
                            logger.info(f"In-game notification sent to {player_ign} about assigned screenshare {ss_info['id']}")
                    
                    logger.info(f'Assigned screensharer {screensharer_id} to screenshare {target_id}')
                    return True, "Screensharer assigned successfully"
                return False, "Failed to update screenshare in database"

            except Exception as e:
                logger.error(f'Error assigning screensharer: {e}')
                return False, f"Error assigning screensharer: {str(e)}"

    async def end_screenshare(self, target_id: str, result: str, channel_id: str) -> Tuple[bool, str]:
        async with self._lock:
            try:
                if target_id not in self.active_screenshares:
                    return False, "No active screenshare found"

                ss_info = self.active_screenshares[target_id]
                if ss_info['state'] != ScreenshareState.IN_PROGRESS:
                    return False, f"Screenshare is in {ss_info['state']} state"

                if str(ss_info['channel_id']) != str(channel_id):
                    return False, "Channel ID mismatch"

                current_time = Timestamp(int(datetime.now().timestamp()), 1)
                
                
                update_result = self.db.update_one(
                    'screenshares',
                    {
                        'target_id': str(target_id),
                        'channel_id': str(channel_id),
                        'state': ScreenshareState.IN_PROGRESS
                    },
                    {'$set': {
                        'state': ScreenshareState.COMPLETED,
                        'result': result,
                        'end_time': current_time,
                        'is_frozen': False,
                        'updated_at': current_time
                    }}
                )

                if update_result:
                    
                    if self.websocket_enabled and self.ws_manager:
                        player_data = self.db.find_one('users', {'discordid': str(target_id)})
                        if player_data and player_data.get('ign'):
                            player_ign = player_data.get('ign')
                            
                            notification_message = f"Your screenshare has been completed with result: {result}"
                            await self.ws_manager.send_player_notification(player_ign, notification_message)
                            logger.info(f"In-game notification sent to {player_ign} about completed screenshare {ss_info['id']}")
                    
                    del self.active_screenshares[target_id]
                    logger.info(f'Ended screenshare {target_id} with result: {result}')
                    return True, "Screenshare ended successfully"
                return False, "Failed to update screenshare in database"

            except Exception as e:
                logger.error(f'Error ending screenshare: {e}')
                return False, f"Error ending screenshare: {str(e)}"

    def is_active(self, target_id: str) -> bool:
        return target_id in self.active_screenshares

    def get_state(self, target_id: str) -> Optional[str]:
        if not self.is_active(target_id):
            return None
        return self.active_screenshares[target_id]['state']

    def get_screenshare_info(self, target_id: str) -> Optional[dict]:
        return self.active_screenshares.get(target_id)
