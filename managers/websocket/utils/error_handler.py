
import asyncio
import json
import logging
import traceback
import time
from typing import Optional, Any, Dict, List, Callable
from websockets.server import WebSocketServerProtocol
from websockets.exceptions import WebSocketException, ConnectionClosed


class WebSocketErrorHandler:
    
    def __init__(self, websocket_manager):
        self.ws_manager = websocket_manager
        self.logger = websocket_manager.logger
        
        
        self.error_counts = {
            'connection_errors': 0,
            'message_errors': 0,
            'timeout_errors': 0,
            'database_errors': 0,
            'json_parse_errors': 0,
            'handler_errors': 0,
            'shutdown_errors': 0
        }
        
        
        self.connection_health = {
            'total_connections': 0,
            'failed_connections': 0,
            'disconnections': 0,
            'last_health_check': time.time()
        }
        
        
        self.recovery_callbacks: Dict[str, List[Callable]] = {
            'connection_lost': [],
            'database_error': [],
            'timeout_error': [],
            'critical_error': []
        }
        
    async def handle_connection_error(self, websocket: Optional[WebSocketServerProtocol], error: Exception) -> None:
        self.error_counts['connection_errors'] += 1
        
        client_address = "unknown"
        connection_info = {}
        
        if websocket:
            try:
                if websocket.remote_address:
                    client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
                    connection_info = {
                        'remote_address': websocket.remote_address,
                        'closed': websocket.closed,
                        'state': str(websocket.state) if hasattr(websocket, 'state') else 'unknown'
                    }
            except Exception as addr_error:
                self.logger.debug(f"Could not determine client address: {addr_error}")
        
        
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'client_address': client_address,
            'connection_info': connection_info,
            'timestamp': time.time(),
            'total_connection_errors': self.error_counts['connection_errors']
        }
        
        self.logger.error(
            f"WebSocket connection error from {client_address}: {type(error).__name__}: {error}. "
            f"Details: {json.dumps(connection_info, default=str)}",
            exc_info=True,
            extra={'error_details': error_details}
        )
        
        
        if isinstance(error, ConnectionClosed):
            self.connection_health['disconnections'] += 1
        else:
            self.connection_health['failed_connections'] += 1
        
        
        if websocket:
            self.ws_manager.clients.discard(websocket)
            
            
            try:
                if not websocket.closed:
                    await websocket.close(code=1011, reason="Internal server error")
            except Exception as close_error:
                self.logger.debug(f"Error closing connection after error: {close_error}")
        
        
        await self._execute_recovery_callbacks('connection_lost', {
            'websocket': websocket,
            'error': error,
            'client_address': client_address
        })
    
    async def handle_message_error(self, websocket: WebSocketServerProtocol, message: str, error: Exception) -> None:
        self.error_counts['message_errors'] += 1
        
        
        if isinstance(error, json.JSONDecodeError):
            self.error_counts['json_parse_errors'] += 1
            error_category = "JSON_PARSE_ERROR"
        elif isinstance(error, MessageValidationError):
            error_category = "MESSAGE_VALIDATION_ERROR"
        elif isinstance(error, HandlerNotFoundError):
            self.error_counts['handler_errors'] += 1
            error_category = "HANDLER_NOT_FOUND_ERROR"
        else:
            error_category = "MESSAGE_PROCESSING_ERROR"
        
        client_address = "unknown"
        try:
            if websocket.remote_address:
                client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        except Exception:
            pass
        
        
        truncated_message = message[:500] + "..." if len(message) > 500 else message
        message_info = {
            'length': len(message),
            'truncated': len(message) > 500,
            'preview': truncated_message
        }
        
        
        message_type = "unknown"
        try:
            if not isinstance(error, json.JSONDecodeError):
                parsed = json.loads(message)
                message_type = parsed.get('type', 'unknown')
        except:
            pass
        
        error_details = {
            'error_category': error_category,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'client_address': client_address,
            'message_type': message_type,
            'message_info': message_info,
            'timestamp': time.time(),
            'total_message_errors': self.error_counts['message_errors']
        }
        
        
        if isinstance(error, json.JSONDecodeError):
            self.logger.error(
                f"JSON parsing error from {client_address}: Invalid JSON at line {error.lineno}, "
                f"column {error.colno}. Message preview: {truncated_message}",
                exc_info=True,
                extra={'error_details': error_details}
            )
        else:
            self.logger.error(
                f"Message processing error from {client_address}: {type(error).__name__}: {error}. "
                f"Message type: {message_type}, Preview: {truncated_message}",
                exc_info=True,
                extra={'error_details': error_details}
            )
        
        
        try:
            if isinstance(error, json.JSONDecodeError):
                error_response = {
                    "type": "error",
                    "error": "Invalid JSON format",
                    "details": f"JSON parsing failed at line {error.lineno}, column {error.colno}" if self.ws_manager.config.get('debug', False) else "Invalid message format"
                }
            elif isinstance(error, MessageValidationError):
                error_response = {
                    "type": "error",
                    "error": "Message validation failed",
                    "details": str(error) if self.ws_manager.config.get('debug', False) else "Invalid message structure"
                }
            elif isinstance(error, HandlerNotFoundError):
                error_response = {
                    "type": "error",
                    "error": "Unknown message type",
                    "details": str(error) if self.ws_manager.config.get('debug', False) else "Message type not supported"
                }
            else:
                error_response = {
                    "type": "error",
                    "error": "Message processing failed",
                    "details": str(error) if self.ws_manager.config.get('debug', False) else "Internal processing error"
                }
            
            await self.ws_manager.send_to_client(websocket, error_response)
            
        except Exception as response_error:
            self.logger.debug(f"Could not send error response to client: {response_error}")
            
    
    async def handle_timeout_error(self, request_id: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        self.error_counts['timeout_errors'] += 1
        
        timeout_details = {
            'request_id': request_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'timestamp': time.time(),
            'total_timeout_errors': self.error_counts['timeout_errors']
        }
        
        self.logger.warning(
            f"Request timeout for request_id {request_id}: {type(error).__name__}: {error}. "
            f"Context: {json.dumps(context or {}, default=str)}",
            extra={'timeout_details': timeout_details}
        )
        
        
        if hasattr(self.ws_manager, 'callback_manager'):
            try:
                self.ws_manager.callback_manager.reject_request(request_id, error)
                self.logger.debug(f"Cleaned up callback for timed-out request {request_id}")
            except Exception as cleanup_error:
                self.logger.debug(f"Error cleaning up callback for request {request_id}: {cleanup_error}")
        
        
        await self._cleanup_timeout_resources(request_id, context)
        
        
        await self._execute_recovery_callbacks('timeout_error', {
            'request_id': request_id,
            'error': error,
            'context': context
        })
    
    async def _cleanup_timeout_resources(self, request_id: str, context: Optional[Dict[str, Any]]) -> None:
        try:
            
            if hasattr(self.ws_manager, 'warp_timeouts') and request_id in self.ws_manager.warp_timeouts:
                del self.ws_manager.warp_timeouts[request_id]
                self.logger.debug(f"Cleaned up warp timeout for request {request_id}")
            
            
            if context and 'game_id' in context:
                game_id = context['game_id']
                
                
                if hasattr(self.ws_manager, 'warp_attempts') and game_id in self.ws_manager.warp_attempts:
                    del self.ws_manager.warp_attempts[game_id]
                    self.logger.debug(f"Cleaned up warp attempts for game {game_id}")
                
                
                if hasattr(self.ws_manager, 'team_data') and game_id in self.ws_manager.team_data:
                    del self.ws_manager.team_data[game_id]
                    self.logger.debug(f"Cleaned up team data for game {game_id}")
            
        except Exception as cleanup_error:
            self.logger.debug(f"Error during timeout resource cleanup: {cleanup_error}")
    
    async def handle_database_error(self, operation: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        self.error_counts['database_errors'] += 1
        
        database_error_details = {
            'operation': operation,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'timestamp': time.time(),
            'total_database_errors': self.error_counts['database_errors']
        }
        
        self.logger.error(
            f"Database error during {operation}: {type(error).__name__}: {error}. "
            f"Context: {json.dumps(context or {}, default=str)}",
            exc_info=True,
            extra={'database_error_details': database_error_details}
        )
        
        
        transient_errors = [
            'ConnectionError', 'TimeoutError', 'NetworkTimeout', 
            'ServerSelectionTimeoutError', 'AutoReconnect'
        ]
        
        is_transient = any(error_type in type(error).__name__ for error_type in transient_errors)
        
        if is_transient:
            self.logger.info(f"Database error appears transient, marking for potential retry: {operation}")
            
            
            await self._execute_recovery_callbacks('database_error', {
                'operation': operation,
                'error': error,
                'context': context,
                'is_transient': True
            })
        else:
            self.logger.warning(f"Database error appears permanent, no retry recommended: {operation}")
            
            
            await self._execute_recovery_callbacks('database_error', {
                'operation': operation,
                'error': error,
                'context': context,
                'is_transient': False
            })
    
    def log_error(self, error_type: str, details: str, exception: Optional[Exception] = None) -> None:
        log_message = f"[{error_type}] {details}"
        
        if exception:
            self.logger.error(log_message, exc_info=True)
        else:
            self.logger.error(log_message)
    
    def log_warning(self, warning_type: str, details: str) -> None:
        self.logger.warning(f"[{warning_type}] {details}")
    
    def log_debug(self, debug_type: str, details: str) -> None:
        self.logger.debug(f"[{debug_type}] {details}")
    
    async def handle_shutdown_error(self, component: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        self.error_counts['shutdown_errors'] += 1
        
        shutdown_details = {
            'component': component,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'timestamp': time.time(),
            'total_shutdown_errors': self.error_counts['shutdown_errors']
        }
        
        self.logger.error(
            f"Shutdown error in {component}: {type(error).__name__}: {error}. "
            f"Context: {json.dumps(context or {}, default=str)}",
            exc_info=True,
            extra={'shutdown_details': shutdown_details}
        )
        
        
        self.logger.info(f"Continuing shutdown process despite error in {component}")
    
    async def monitor_connection_health(self) -> Dict[str, Any]:
        current_time = time.time()
        self.connection_health['last_health_check'] = current_time
        
        
        current_connections = len(self.ws_manager.clients) if hasattr(self.ws_manager, 'clients') else 0
        
        health_report = {
            'current_connections': current_connections,
            'total_connections': self.connection_health['total_connections'],
            'failed_connections': self.connection_health['failed_connections'],
            'disconnections': self.connection_health['disconnections'],
            'last_health_check': current_time,
            'error_counts': self.error_counts.copy(),
            'connection_success_rate': self._calculate_connection_success_rate(),
            'uptime_seconds': current_time - getattr(self.ws_manager, 'start_time', current_time)
        }
        
        
        if hasattr(self, '_last_health_log'):
            if current_time - self._last_health_log > 300:  
                self._log_health_report(health_report)
                self._last_health_log = current_time
        else:
            self._last_health_log = current_time
        
        return health_report
    
    def _calculate_connection_success_rate(self) -> float:
        total_attempts = self.connection_health['total_connections']
        if total_attempts == 0:
            return 100.0
        
        successful = total_attempts - self.connection_health['failed_connections']
        return (successful / total_attempts) * 100.0
    
    def _log_health_report(self, health_report: Dict[str, Any]) -> None:
        success_rate = health_report['connection_success_rate']
        total_errors = sum(self.error_counts.values())
        
        self.logger.info(
            f"WebSocket Health Report - Connections: {health_report['current_connections']} active, "
            f"{health_report['total_connections']} total, {success_rate:.1f}% success rate. "
            f"Errors: {total_errors} total ({self.error_counts})"
        )
        
        
        if success_rate < 90.0 and health_report['total_connections'] > 10:
            self.logger.warning(f"Low connection success rate: {success_rate:.1f}%")
        
        if total_errors > 100:
            self.logger.warning(f"High error count detected: {total_errors} total errors")
    
    def register_recovery_callback(self, error_type: str, callback: Callable) -> None:
        if error_type not in self.recovery_callbacks:
            self.recovery_callbacks[error_type] = []
        
        self.recovery_callbacks[error_type].append(callback)
        self.logger.debug(f"Registered recovery callback for error type: {error_type}")
    
    def unregister_recovery_callback(self, error_type: str, callback: Callable) -> None:
        if error_type in self.recovery_callbacks:
            try:
                self.recovery_callbacks[error_type].remove(callback)
                self.logger.debug(f"Unregistered recovery callback for error type: {error_type}")
            except ValueError:
                self.logger.debug(f"Recovery callback not found for error type: {error_type}")
    
    async def _execute_recovery_callbacks(self, error_type: str, context: Dict[str, Any]) -> None:
        if error_type not in self.recovery_callbacks:
            return
        
        callbacks = self.recovery_callbacks[error_type].copy()
        if not callbacks:
            return
        
        self.logger.debug(f"Executing {len(callbacks)} recovery callbacks for error type: {error_type}")
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(context)
                else:
                    callback(context)
            except Exception as callback_error:
                self.logger.error(
                    f"Error in recovery callback for {error_type}: {callback_error}",
                    exc_info=True
                )
    
    def get_error_statistics(self) -> Dict[str, Any]:
        return {
            'error_counts': self.error_counts.copy(),
            'connection_health': self.connection_health.copy(),
            'recovery_callbacks': {
                error_type: len(callbacks) 
                for error_type, callbacks in self.recovery_callbacks.items()
            }
        }
    
    def reset_error_statistics(self) -> None:
        self.logger.info("Resetting error statistics")
        
        for key in self.error_counts:
            self.error_counts[key] = 0
        
        self.connection_health.update({
            'total_connections': 0,
            'failed_connections': 0,
            'disconnections': 0,
            'last_health_check': time.time()
        })
    
    async def handle_critical_error(self, component: str, error: Exception, should_shutdown: bool = False) -> None:
        critical_details = {
            'component': component,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'should_shutdown': should_shutdown,
            'timestamp': time.time()
        }
        
        self.logger.critical(
            f"CRITICAL ERROR in {component}: {type(error).__name__}: {error}. "
            f"Shutdown required: {should_shutdown}",
            exc_info=True,
            extra={'critical_details': critical_details}
        )
        
        
        await self._execute_recovery_callbacks('critical_error', {
            'component': component,
            'error': error,
            'should_shutdown': should_shutdown
        })
        
        if should_shutdown:
            self.logger.critical("Initiating emergency shutdown due to critical error")
            
    
    def track_connection_attempt(self, success: bool) -> None:
        self.connection_health['total_connections'] += 1
        if not success:
            self.connection_health['failed_connections'] += 1


class WebSocketException(Exception):
    pass


class MessageValidationError(WebSocketException):
    pass


class HandlerNotFoundError(WebSocketException):
    pass


class ConnectionError(WebSocketException):
    pass


class TimeoutError(WebSocketException):
    pass
