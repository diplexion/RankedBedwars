
import asyncio
import logging
from typing import Dict, Any, Optional
from websockets.server import WebSocketServerProtocol
import discord

from ..models.messages import MessageType, MessageBuilder
from ..utils.error_handler import MessageValidationError


class VoiceHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.bot = websocket_manager.bot
        self.logger = logging.getLogger(__name__)
        
        
        self.db_manager = self.bot.database_manager
        
        
        self._register_handlers()
    
    def _register_handlers(self):
        self.ws_manager.register_handler(MessageType.CALL_CMD, self.handle_call_command)
        self.ws_manager.register_handler(MessageType.CALL_SUCCESS, self.handle_call_success)
        self.ws_manager.register_handler(MessageType.CALL_FAILURE, self.handle_call_failure)
        
        self.logger.info("VoiceHandler registered message handlers")
    
    async def handle_call_command(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            requester_ign = message.get('requester_ign')
            target_ign = message.get('target_ign')
            
            if not requester_ign:
                raise MessageValidationError("callcmd message missing 'requester_ign' field")
            
            if not target_ign:
                raise MessageValidationError("callcmd message missing 'target_ign' field")
            
            self.logger.debug(f"Processing call command from {requester_ign} to {target_ign}")
            
            
            validation_result = await self._validate_call_request(requester_ign, target_ign)
            
            if not validation_result['valid']:
                
                failure_message = MessageBuilder.build_call_failure(
                    requester_ign, 
                    target_ign, 
                    validation_result['reason']
                )
                await self.ws_manager.send_to_client(websocket, failure_message)
                self.logger.debug(f"Call command failed: {validation_result['reason']}")
                return
            
            
            permission_result = await self._grant_voice_permissions(
                validation_result['requester_id'], 
                validation_result['target_id']
            )
            
            if permission_result['success']:
                
                success_message = MessageBuilder.build_call_success(requester_ign, target_ign)
                await self.ws_manager.send_to_client(websocket, success_message)
                
                
                await self._notify_game_channel(
                    validation_result['requester_id'],
                    validation_result['target_id'],
                    requester_ign,
                    target_ign,
                    permission_result['channel_name']
                )
                
                self.logger.info(f"Successfully granted voice permissions from {requester_ign} to {target_ign}")
            else:
                
                failure_message = MessageBuilder.build_call_failure(
                    requester_ign, 
                    target_ign, 
                    permission_result['reason']
                )
                await self.ws_manager.send_to_client(websocket, failure_message)
                self.logger.debug(f"Voice permission grant failed: {permission_result['reason']}")
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in call command handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling call command message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_call_success(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            requester_ign = message.get('requester_ign')
            target_ign = message.get('target_ign')
            
            if not requester_ign:
                raise MessageValidationError("call_success message missing 'requester_ign' field")
            
            if not target_ign:
                raise MessageValidationError("call_success message missing 'target_ign' field")
            
            self.logger.info(f"Call success confirmed: {requester_ign} -> {target_ign}")
            
            
            await self._log_call_event(requester_ign, target_ign, "success")
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in call success handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling call success message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def handle_call_failure(self, message: Dict[str, Any], websocket: WebSocketServerProtocol) -> None:
        try:
            
            requester_ign = message.get('requester_ign')
            target_ign = message.get('target_ign')
            reason = message.get('reason', 'Unknown reason')
            
            if not requester_ign:
                raise MessageValidationError("call_failure message missing 'requester_ign' field")
            
            if not target_ign:
                raise MessageValidationError("call_failure message missing 'target_ign' field")
            
            self.logger.warning(f"Call failure confirmed: {requester_ign} -> {target_ign}, reason: {reason}")
            
            
            await self._log_call_event(requester_ign, target_ign, "failure", reason)
            
        except MessageValidationError as e:
            self.logger.error(f"Validation error in call failure handler: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
        except Exception as e:
            self.logger.error(f"Error handling call failure message: {e}")
            await self.ws_manager.error_handler.handle_message_error(websocket, str(message), e)
    
    async def _validate_call_request(self, requester_ign: str, target_ign: str) -> Dict[str, Any]:
        try:
            
            try:
                requester_data = self.db_manager.find_one('users', {'ign': {'$regex': f'^{requester_ign}$', '$options': 'i'}})
            except Exception as db_error:
                await self.ws_manager.error_handler.handle_database_error(
                    f"lookup requester {requester_ign}", 
                    db_error, 
                    {'operation': 'find_one', 'collection': 'users', 'ign': requester_ign}
                )
                return {
                    'valid': False,
                    'reason': 'Database error looking up requester'
                }
            
            if not requester_data:
                return {
                    'valid': False,
                    'reason': f'Requester player {requester_ign} not found in database'
                }
            
            
            try:
                target_data = self.db_manager.find_one('users', {'ign': {'$regex': f'^{target_ign}$', '$options': 'i'}})
            except Exception as db_error:
                await self.ws_manager.error_handler.handle_database_error(
                    f"lookup target {target_ign}", 
                    db_error, 
                    {'operation': 'find_one', 'collection': 'users', 'ign': target_ign}
                )
                return {
                    'valid': False,
                    'reason': 'Database error looking up target'
                }
            
            if not target_data:
                return {
                    'valid': False,
                    'reason': f'Target player {target_ign} not found in database'
                }
            
            requester_id = requester_data['discordid']
            target_id = target_data['discordid']
            
            
            guild = None
            requester_member = None
            target_member = None
            
            
            for guild_obj in self.bot.guilds:
                req_member = guild_obj.get_member(int(requester_id))
                tgt_member = guild_obj.get_member(int(target_id))
                
                if req_member and tgt_member:
                    guild = guild_obj
                    requester_member = req_member
                    target_member = tgt_member
                    break
            
            if not guild or not requester_member or not target_member:
                return {
                    'valid': False,
                    'reason': 'Both players must be in the same Discord server'
                }
            
            
            
            if requester_member.bot:
                return {
                    'valid': False,
                    'reason': 'Bot accounts cannot make voice calls'
                }
            
            
            if target_member.bot:
                return {
                    'valid': False,
                    'reason': 'Cannot call bot accounts'
                }
            
            
            
            
            return {
                'valid': True,
                'requester_id': requester_id,
                'target_id': target_id,
                'guild': guild,
                'requester_member': requester_member,
                'target_member': target_member
            }
            
        except Exception as e:
            self.logger.error(f"Error validating call request: {e}")
            return {
                'valid': False,
                'reason': f'Internal error during validation: {str(e)}'
            }    

    async def _grant_voice_permissions(self, requester_id: str, target_id: str) -> Dict[str, Any]:
        try:
            
            game_channel_data = await self._find_active_game_channel(requester_id)
            
            if not game_channel_data:
                return {
                    'success': False,
                    'reason': 'Requester is not in an active game'
                }
            
            
            guild = self.bot.get_guild(game_channel_data['guild_id'])
            if not guild:
                return {
                    'success': False,
                    'reason': 'Could not find Discord server'
                }
            
            target_member = guild.get_member(int(target_id))
            if not target_member:
                return {
                    'success': False,
                    'reason': 'Target player not found in Discord server'
                }
            
            
            team1_voice_id = game_channel_data.get('team1voicechannelid')
            team2_voice_id = game_channel_data.get('team2voicechannelid')
            
            
            voice_channel = None
            channel_name = None
            
            
            if team1_voice_id:
                team1_channel = guild.get_channel(int(team1_voice_id))
                if team1_channel and any(member.id == int(requester_id) for member in team1_channel.members):
                    voice_channel = team1_channel
                    channel_name = "Team 1"
            
            
            if not voice_channel and team2_voice_id:
                team2_channel = guild.get_channel(int(team2_voice_id))
                if team2_channel and any(member.id == int(requester_id) for member in team2_channel.members):
                    voice_channel = team2_channel
                    channel_name = "Team 2"
            
            
            if not voice_channel:
                
                channels_granted = []
                
                if team1_voice_id:
                    team1_channel = guild.get_channel(int(team1_voice_id))
                    if team1_channel:
                        await team1_channel.set_permissions(
                            target_member, 
                            connect=True, 
                            speak=True,
                            view_channel=True
                        )
                        channels_granted.append("Team 1")
                
                if team2_voice_id:
                    team2_channel = guild.get_channel(int(team2_voice_id))
                    if team2_channel:
                        await team2_channel.set_permissions(
                            target_member, 
                            connect=True, 
                            speak=True,
                            view_channel=True
                        )
                        channels_granted.append("Team 2")
                
                if channels_granted:
                    return {
                        'success': True,
                        'channel_name': f"Game channels ({', '.join(channels_granted)})",
                        'granted_channels': channels_granted
                    }
                else:
                    return {
                        'success': False,
                        'reason': 'No valid voice channels found for the game'
                    }
            
            
            await voice_channel.set_permissions(
                target_member, 
                connect=True, 
                speak=True,
                view_channel=True
            )
            
            self.logger.info(f"Granted voice permissions to {target_id} in {voice_channel.name}")
            
            return {
                'success': True,
                'channel_name': channel_name,
                'channel_id': voice_channel.id
            }
            
        except discord.Forbidden:
            return {
                'success': False,
                'reason': 'Bot lacks permission to modify voice channel permissions'
            }
        except discord.NotFound:
            return {
                'success': False,
                'reason': 'Voice channel not found'
            }
        except Exception as e:
            self.logger.error(f"Error granting voice permissions: {e}")
            return {
                'success': False,
                'reason': f'Internal error: {str(e)}'
            }
    
    async def _find_active_game_channel(self, player_id: str) -> Optional[Dict[str, Any]]:
        try:
            
            
            
            
            for guild in self.bot.guilds:
                member = guild.get_member(int(player_id))
                if not member or not member.voice or not member.voice.channel:
                    continue
                
                voice_channel_id = str(member.voice.channel.id)
                
                
                game_channel = self.db_manager.find_one('gameschannels', {
                    '$or': [
                        {'team1voicechannelid': voice_channel_id},
                        {'team2voicechannelid': voice_channel_id},
                        {'pickingvoicechannelid': voice_channel_id}
                    ]
                })
                
                if game_channel:
                    
                    game_channel['guild_id'] = guild.id
                    return game_channel
            
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding active game channel for player {player_id}: {e}")
            return None
    
    async def _notify_game_channel(
        self, 
        requester_id: str, 
        target_id: str, 
        requester_ign: str, 
        target_ign: str, 
        channel_name: str
    ) -> None:
        try:
            
            game_channel_data = await self._find_active_game_channel(requester_id)
            
            if not game_channel_data:
                self.logger.debug("No active game channel found for notification")
                return
            
            text_channel_id = game_channel_data.get('textchannelid')
            if not text_channel_id:
                self.logger.debug("No text channel ID found in game channel data")
                return
            
            
            text_channel = self.bot.get_channel(int(text_channel_id))
            if not text_channel:
                self.logger.debug(f"Text channel {text_channel_id} not found")
                return
            
            
            notification_message = (
                f"🎤 **Voice Call Granted**\n"
                f"**{requester_ign}** has granted voice permissions to **{target_ign}** in {channel_name}.\n"
                f"<@{target_id}> can now join and speak in the voice channel."
            )
            
            
            await text_channel.send(notification_message)
            
            self.logger.info(f"Sent voice permission notification to game channel {text_channel_id}")
            
        except discord.Forbidden:
            self.logger.warning("Bot lacks permission to send messages to game channel")
        except discord.NotFound:
            self.logger.warning("Game text channel not found")
        except Exception as e:
            self.logger.error(f"Error sending game channel notification: {e}")
    
    async def _log_call_event(
        self, 
        requester_ign: str, 
        target_ign: str, 
        event_type: str, 
        reason: Optional[str] = None
    ) -> None:
        try:
            log_message = f"Voice call {event_type}: {requester_ign} -> {target_ign}"
            if reason:
                log_message += f" (reason: {reason})"
            
            if event_type == "success":
                self.logger.info(log_message)
            else:
                self.logger.warning(log_message)
            
            
            
        except Exception as e:
            self.logger.error(f"Error logging call event: {e}")
    
    async def send_call_command(
        self, 
        requester_ign: str, 
        target_ign: str, 
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        if not self.ws_manager.is_enabled():
            raise Exception("WebSocket system is disabled")
        
        try:
            self.logger.debug(f"Sending call command: {requester_ign} -> {target_ign}")
            
            
            response = await self.ws_manager.send_request_with_response(
                message_type=MessageType.CALL_CMD,
                message_data={
                    'requester_ign': requester_ign,
                    'target_ign': target_ign
                },
                timeout=timeout
            )
            
            self.logger.debug(f"Call command response received: {response}")
            return response
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Timeout sending call command: {requester_ign} -> {target_ign}")
            raise
        except Exception as e:
            self.logger.error(f"Error sending call command: {e}")
            raise e
    
    def get_handler_status(self) -> Dict[str, Any]:
        return {
            'handler_name': 'VoiceHandler',
            'registered_message_types': [
                MessageType.CALL_CMD,
                MessageType.CALL_SUCCESS,
                MessageType.CALL_FAILURE
            ],
            'websocket_enabled': self.ws_manager.is_enabled()
        }
    
    async def cleanup(self) -> None:
        try:
            
            self.ws_manager.unregister_handler(MessageType.CALL_CMD)
            self.ws_manager.unregister_handler(MessageType.CALL_SUCCESS)
            self.ws_manager.unregister_handler(MessageType.CALL_FAILURE)
            
            self.logger.debug("VoiceHandler cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during VoiceHandler cleanup: {e}")
