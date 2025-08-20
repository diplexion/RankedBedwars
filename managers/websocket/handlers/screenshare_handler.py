
import logging
from typing import Dict, Any, Optional
from ..models.messages import MessageType
from ..utils.error_handler import WebSocketErrorHandler

class ScreenshareHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.bot = websocket_manager.bot
        self.logger = logging.getLogger(__name__)
        self.error_handler = WebSocketErrorHandler(websocket_manager)
        
        
        self.screenshare_manager = getattr(self.bot, 'screenshare_manager', None)
        if not self.screenshare_manager:
            self.logger.warning("Screenshare manager not found on bot instance")
    
    async def handle_auto_ss(self, message: Dict[str, Any], websocket) -> None:
        try:
            target_ign = message.get('target_ign')
            requester_ign = message.get('requester_ign')
            
            if not target_ign or not requester_ign:
                await self._send_ss_error(websocket, "Missing target_ign or requester_ign", message)
                return
            
            self.logger.info(f"Processing autoss request: {requester_ign} -> {target_ign}")
            
            
            target_id = await self._get_discord_id_from_ign(target_ign)
            requester_id = await self._get_discord_id_from_ign(requester_ign)
            
            if not target_id:
                await self._send_ss_error(websocket, f"Target player {target_ign} not found", message)
                return
                
            if not requester_id:
                await self._send_ss_error(websocket, f"Requester {requester_ign} not found", message)
                return
            
            
            if not self.screenshare_manager:
                await self._send_ss_error(websocket, "Screenshare system not available", message)
                return
            
            
            success, result = await self.screenshare_manager.create_screenshare(
                target_id=target_id,
                requester_id=requester_id,
                reason="Automatic screenshare request from game",
                image_url=""  
            )
            
            if success:
                self.logger.info(f"Created screenshare {result} for {target_ign} (ID: {target_id})")
                await self._send_ss_success(websocket, target_ign, requester_ign, result)
            else:
                self.logger.warning(f"Failed to create screenshare for {target_ign}: {result}")
                await self._send_ss_error(websocket, result, message)
                
        except Exception as e:
            self.logger.error(f"Error handling autoss message: {e}")
            await self.error_handler.handle_message_error(websocket, message, e)
            await self._send_ss_error(websocket, f"Internal error: {str(e)}", message)
    
    async def handle_screenshare_dontlog(self, message: Dict[str, Any], websocket) -> None:
        try:
            target_ign = message.get('target_ign')
            enabled = message.get('enabled', True)
            
            if not target_ign:
                await self._send_dontlog_error(websocket, "Missing target_ign", message)
                return
            
            self.logger.info(f"Processing screensharedontlog request: {target_ign}, enabled: {enabled}")
            
            
            target_id = await self._get_discord_id_from_ign(target_ign)
            
            if not target_id:
                await self._send_dontlog_error(websocket, f"Target player {target_ign} not found", message)
                return
            
            
            if not self.screenshare_manager:
                await self._send_dontlog_error(websocket, "Screenshare system not available", message)
                return
            
            
            ss_info = self.screenshare_manager.get_screenshare_info(target_id)
            
            if not ss_info:
                await self._send_dontlog_error(websocket, f"No active screenshare found for {target_ign}", message)
                return
            
            
            
            
            try:
                update_result = self.bot.database_manager.update_one(
                    'screenshares',
                    {'target_id': str(target_id), 'state': {'$in': ['pending', 'in_progress']}},
                    {'$set': {'dont_log': not enabled}}
                )
                
                if update_result:
                    self.logger.info(f"Updated logging status for {target_ign}: dont_log = {not enabled}")
                    await self._send_dontlog_success(websocket, target_ign, enabled)
                else:
                    await self._send_dontlog_error(websocket, f"Failed to update logging status for {target_ign}", message)
                    
            except Exception as db_error:
                self.logger.error(f"Database error updating logging status: {db_error}")
                await self._send_dontlog_error(websocket, f"Database error: {str(db_error)}", message)
                
        except Exception as e:
            self.logger.error(f"Error handling screensharedontlog message: {e}")
            await self.error_handler.handle_message_error(websocket, message, e)
            await self._send_dontlog_error(websocket, f"Internal error: {str(e)}", message)
    
    async def _get_discord_id_from_ign(self, ign: str) -> Optional[str]:
        try:
            user_data = self.bot.database_manager.find_one('users', {'ign': ign})
            if user_data and 'discordid' in user_data:
                return str(user_data['discordid'])
            return None
        except Exception as e:
            self.logger.error(f"Error looking up Discord ID for IGN {ign}: {e}")
            return None
    
    async def _send_ss_success(self, websocket, target_ign: str, requester_ign: str, screenshare_id: str) -> None:
        try:
            response = {
                "type": MessageType.AUTOSS_SUCCESS,
                "target_ign": target_ign,
                "requester_ign": requester_ign,
                "screenshare_id": screenshare_id,
                "message": f"Screenshare created successfully for {target_ign}"
            }
            await websocket.send(self.ws_manager._serialize_message(response))
        except Exception as e:
            self.logger.error(f"Error sending screenshare success response: {e}")
    
    async def _send_ss_error(self, websocket, error_message: str, original_message: Dict[str, Any]) -> None:
        try:
            response = {
                "type": MessageType.AUTOSS_ERROR,
                "error": error_message,
                "target_ign": original_message.get('target_ign', ''),
                "requester_ign": original_message.get('requester_ign', '')
            }
            await websocket.send(self.ws_manager._serialize_message(response))
        except Exception as e:
            self.logger.error(f"Error sending screenshare error response: {e}")
    
    async def _send_dontlog_success(self, websocket, target_ign: str, enabled: bool) -> None:
        try:
            response = {
                "type": MessageType.SCREENSHAREDONTLOG_SUCCESS,
                "target_ign": target_ign,
                "enabled": enabled,
                "message": f"Logging {'enabled' if enabled else 'disabled'} for {target_ign}"
            }
            await websocket.send(self.ws_manager._serialize_message(response))
        except Exception as e:
            self.logger.error(f"Error sending dontlog success response: {e}")
    
    async def _send_dontlog_error(self, websocket, error_message: str, original_message: Dict[str, Any]) -> None:
        try:
            response = {
                "type": MessageType.SCREENSHAREDONTLOG_ERROR,
                "error": error_message,
                "target_ign": original_message.get('target_ign', '')
            }
            await websocket.send(self.ws_manager._serialize_message(response))
        except Exception as e:
            self.logger.error(f"Error sending dontlog error response: {e}")
