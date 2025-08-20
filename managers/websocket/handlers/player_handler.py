
import asyncio
import logging
from typing import Dict, Any, Optional
from websockets.server import WebSocketServerProtocol

from ..models.messages import MessageType, MessageBuilder
from ..utils.error_handler import MessageValidationError


class PlayerHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.bot = websocket_manager.bot
        self.logger = logging.getLogger(__name__)
        
        
        self._register_handlers()
    
    def _register_handlers(self):
        self.ws_manager.register_handler(MessageType.CHECK_PLAYER, self.handle_check_player)
        self.ws_manager.register_handler(MessageType.PLAYER_STATUS, self.handle_player_status)
        self.ws_manager.register_handler(MessageType.VERIFICATION, self.handle_verification)
        
        self.logger.info("PlayerHandler registered message handlers")
    
    async def handle_check_player(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            ign = message.get('ign')
            request_id = message.get('request_id')
            
            if not ign:
                raise MessageValidationError("check_player message missing 'ign' field")
            
            if not request_id:
                raise MessageValidationError("check_player message missing 'request_id' field")
            
            self.logger.debug(f"Processing check_player request for {ign} (request_id: {request_id})")
            
            
            check_message = MessageBuilder.build_check_player(ign, request_id)
            
            
            await self.ws_manager.broadcast(check_message)
            
            self.logger.debug(f"Broadcasted check_player request for {ign}")
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in check_player handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling check_player message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_player_status(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            ign = message.get('ign')
            online = message.get('online')
            request_id = message.get('request_id')
            
            if not ign:
                raise MessageValidationError("player_status message missing 'ign' field")
            
            if online is None:
                raise MessageValidationError("player_status message missing 'online' field")
            
            if not request_id:
                raise MessageValidationError("player_status message missing 'request_id' field")
            
            self.logger.debug(f"Processing player_status response for {ign}: online={online} (request_id: {request_id})")
            
            
            request_info = self.ws_manager.callback_manager.get_request_info(request_id)
            if request_info:
                
                response_data = {
                    'ign': ign,
                    'online': online,
                    'type': MessageType.PLAYER_STATUS
                }
                
                
                success = self.ws_manager.callback_manager.resolve_request(request_id, response_data)
                if success:
                    self.logger.debug(f"Resolved player_status callback for {ign} (request_id: {request_id})")
                else:
                    self.logger.warning(f"Failed to resolve player_status callback for {ign} (request_id: {request_id})")
            else:
                
                self.logger.debug(f"Received unsolicited player_status for {ign}: online={online}")
                await self._handle_unsolicited_player_status(ign, online)
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in player_status handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling player_status message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_verification(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            ign = message.get('ign')
            discord_id = message.get('discord_id')
            verified = message.get('verified')
            
            if not ign:
                raise MessageValidationError("verification message missing 'ign' field")
            
            if not discord_id:
                raise MessageValidationError("verification message missing 'discord_id' field")
            
            if verified is None:
                raise MessageValidationError("verification message missing 'verified' field")
            
            self.logger.debug(f"Processing verification for {ign} (discord_id: {discord_id}, verified: {verified})")
            
            
            if verified:
                await self._handle_player_verified(ign, discord_id)
            else:
                await self._handle_player_unverified(ign, discord_id)
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in verification handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling verification message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def check_player_online(self, ign: str, timeout: Optional[float] = None) -> bool:
        if not self.ws_manager.is_enabled():
            raise Exception("WebSocket system is disabled")
        
        try:
            self.logger.debug(f"Checking online status for player: {ign}")
            
            
            response = await self.ws_manager.send_request_with_response(
                message_type=MessageType.CHECK_PLAYER,
                message_data={'ign': ign},
                timeout=timeout
            )
            
            
            online = response.get('online', False)
            self.logger.debug(f"Player {ign} online status: {online}")
            
            return online
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout checking online status for player: {ign}")
            return False  
        except Exception as e:
            self.logger.error(f"Error checking online status for player {ign}: {e}")
            raise e
    
    async def verify_player(self, ign: str, discord_id: str) -> bool:
        if not self.ws_manager.is_enabled():
            raise Exception("WebSocket system is disabled")
        
        try:
            self.logger.debug(f"Sending verification request for {ign} (discord_id: {discord_id})")
            
            
            verification_message = {
                'ign': ign,
                'discord_id': discord_id,
                'verified': True  
            }
            
            
            await self.ws_manager.send_request_no_response(
                message_type=MessageType.VERIFICATION,
                message_data=verification_message
            )
            
            self.logger.debug(f"Sent verification request for {ign}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending verification for player {ign}: {e}")
            raise e
    
    async def _handle_unsolicited_player_status(self, ign: str, online: bool) -> None:
        try:
            self.logger.debug(f"Handling unsolicited status update for {ign}: online={online}")
            
            
            
            if online:
                self.logger.info(f"Player {ign} came online")
            else:
                self.logger.info(f"Player {ign} went offline")
            
            
            
            
        except Exception as e:
            self.logger.error(f"Error handling unsolicited player status for {ign}: {e}")
    
    async def _handle_player_verified(self, ign: str, discord_id: str) -> None:
        try:
            self.logger.info(f"Player {ign} verified with Discord ID: {discord_id}")
            
            
            
            
            
            
            
            
            
        except Exception as e:
            self.logger.error(f"Error handling player verification for {ign}: {e}")
    
    async def _handle_player_unverified(self, ign: str, discord_id: str) -> None:
        try:
            self.logger.warning(f"Player {ign} failed verification with Discord ID: {discord_id}")
            
            
            
            
            
            
            
            
            
        except Exception as e:
            self.logger.error(f"Error handling player unverification for {ign}: {e}")
    
    def get_handler_status(self) -> Dict[str, Any]:
        return {
            'handler_name': 'PlayerHandler',
            'registered_message_types': [
                MessageType.CHECK_PLAYER,
                MessageType.PLAYER_STATUS,
                MessageType.VERIFICATION
            ],
            'websocket_enabled': self.ws_manager.is_enabled()
        }
