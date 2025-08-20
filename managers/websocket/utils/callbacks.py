
import asyncio
import uuid
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PendingRequest:
    request_id: str
    future: asyncio.Future
    created_at: float
    timeout: float
    cleanup_callback: Optional[Callable[[], None]] = None


class CallbackManager:
    
    def __init__(self, default_timeout: float = 60.0):
        self.default_timeout = default_timeout
        self.pending_requests: Dict[str, PendingRequest] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
        self._cleanup_interval = 30.0  
        
    async def start(self):
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Callback manager started")
    
    async def stop(self):
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        
        for request in list(self.pending_requests.values()):
            if not request.future.done():
                request.future.cancel()
                if request.cleanup_callback:
                    try:
                        request.cleanup_callback()
                    except Exception as e:
                        logger.error(f"Error in cleanup callback: {e}")
        
        self.pending_requests.clear()
        logger.info("Callback manager stopped")
    
    def create_request(
        self, 
        timeout: Optional[float] = None,
        cleanup_callback: Optional[Callable[[], None]] = None
    ) -> tuple[str, asyncio.Future]:
        request_id = str(uuid.uuid4())
        future = asyncio.Future()
        timeout_value = timeout if timeout is not None else self.default_timeout
        
        pending_request = PendingRequest(
            request_id=request_id,
            future=future,
            created_at=time.time(),
            timeout=timeout_value,
            cleanup_callback=cleanup_callback
        )
        
        self.pending_requests[request_id] = pending_request
        
        logger.debug(f"Created request {request_id} with timeout {timeout_value}s")
        return request_id, future
    
    def resolve_request(self, request_id: str, result: Any) -> bool:
        pending_request = self.pending_requests.get(request_id)
        if not pending_request:
            logger.warning(f"Attempted to resolve unknown request: {request_id}")
            return False
        
        if pending_request.future.done():
            logger.warning(f"Attempted to resolve already completed request: {request_id}")
            return False
        
        try:
            pending_request.future.set_result(result)
            logger.debug(f"Resolved request {request_id}")
        except Exception as e:
            logger.error(f"Error resolving request {request_id}: {e}")
            return False
        finally:
            
            self._cleanup_request(request_id)
        
        return True
    
    def reject_request(self, request_id: str, exception: Exception) -> bool:
        pending_request = self.pending_requests.get(request_id)
        if not pending_request:
            logger.warning(f"Attempted to reject unknown request: {request_id}")
            return False
        
        if pending_request.future.done():
            logger.warning(f"Attempted to reject already completed request: {request_id}")
            return False
        
        try:
            pending_request.future.set_exception(exception)
            logger.debug(f"Rejected request {request_id} with {type(exception).__name__}")
        except Exception as e:
            logger.error(f"Error rejecting request {request_id}: {e}")
            return False
        finally:
            
            self._cleanup_request(request_id)
        
        return True
    
    def cancel_request(self, request_id: str) -> bool:
        pending_request = self.pending_requests.get(request_id)
        if not pending_request:
            logger.warning(f"Attempted to cancel unknown request: {request_id}")
            return False
        
        if not pending_request.future.done():
            pending_request.future.cancel()
            logger.debug(f"Cancelled request {request_id}")
        
        self._cleanup_request(request_id)
        return True
    
    def get_pending_count(self) -> int:
        return len(self.pending_requests)
    
    def get_request_info(self, request_id: str) -> Optional[Dict[str, Any]]:
        pending_request = self.pending_requests.get(request_id)
        if not pending_request:
            return None
        
        return {
            'request_id': pending_request.request_id,
            'created_at': pending_request.created_at,
            'timeout': pending_request.timeout,
            'age': time.time() - pending_request.created_at,
            'is_done': pending_request.future.done(),
            'is_cancelled': pending_request.future.cancelled()
        }
    
    def _cleanup_request(self, request_id: str):
        pending_request = self.pending_requests.pop(request_id, None)
        if pending_request and pending_request.cleanup_callback:
            try:
                pending_request.cleanup_callback()
            except Exception as e:
                logger.error(f"Error in cleanup callback for request {request_id}: {e}")
    
    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(self._cleanup_interval)
                await self._cleanup_expired_requests()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _cleanup_expired_requests(self):
        current_time = time.time()
        expired_requests = []
        
        for request_id, pending_request in self.pending_requests.items():
            age = current_time - pending_request.created_at
            if age > pending_request.timeout and not pending_request.future.done():
                expired_requests.append((request_id, pending_request))
        
        for request_id, pending_request in expired_requests:
            logger.warning(f"Request {request_id} timed out after {pending_request.timeout}s")
            
            
            if not pending_request.future.done():
                timeout_error = asyncio.TimeoutError(
                    f"Request {request_id} timed out after {pending_request.timeout} seconds"
                )
                pending_request.future.set_exception(timeout_error)
            
            
            self._cleanup_request(request_id)
        
        if expired_requests:
            logger.info(f"Cleaned up {len(expired_requests)} expired requests")


class RequestResponseHandler:
    
    def __init__(self, callback_manager: CallbackManager):
        self.callback_manager = callback_manager
    
    async def send_request_with_response(
        self,
        send_func: Callable[[str, Dict[str, Any]], Awaitable[None]],
        message_type: str,
        message_data: Dict[str, Any],
        timeout: Optional[float] = None,
        cleanup_callback: Optional[Callable[[], None]] = None
    ) -> Any:
        request_id, future = self.callback_manager.create_request(
            timeout=timeout,
            cleanup_callback=cleanup_callback
        )
        
        
        message_with_id = {
            **message_data,
            'request_id': request_id,
            'type': message_type
        }
        
        try:
            
            await send_func(request_id, message_with_id)
            
            
            result = await future
            return result
            
        except Exception as e:
            
            self.callback_manager.cancel_request(request_id)
            raise e
    
    async def send_request_no_response(
        self,
        send_func: Callable[[str, Dict[str, Any]], Awaitable[None]],
        message_type: str,
        message_data: Dict[str, Any]
    ) -> str:
        request_id = str(uuid.uuid4())
        
        message_with_id = {
            **message_data,
            'request_id': request_id,
            'type': message_type
        }
        
        await send_func(request_id, message_with_id)
        return request_id
