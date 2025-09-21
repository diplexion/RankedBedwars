
import json
import logging
from typing import Dict, Any, Optional, Union
from jsonschema import validate, ValidationError, Draft7Validator

class MessageType:
    
    
    CHECK_PLAYER = "CHECK_PLAYER"
    PLAYER_STATUS = "PLAYER_STATUS"
    VERIFICATION = "VERIFICATION"
    
    
    QUEUE_FROM_INGAME = "QUEUEFROMINGAME"
    QUEUE_STATUS = "QUEUESTATUS"
    
    
    WARP_PLAYERS = "WARP_PLAYERS"
    WARP_SUCCESS = "WARP_SUCCESS"
    WARP_FAILED_ARENA = "WARP_FAILED_ARENA_NOT_FOUND"
    WARP_FAILED_OFFLINE = "WARP_FAILED_OFFLINE_PLAYERS"
    RETRY_GAME = "RETRYGAME"
    AUTO_RETRY_FROM_INGAME = "AUTORETRYGAMEFROMINGAME"
    
    
    SCORING = "SCORING"
    VOIDING = "VOIDING"
    
    
    CALL_CMD = "CALL_CMD"
    CALL_SUCCESS = "CALL_SUCCESS"
    CALL_FAILURE = "CALL_FAILURE"
    
    
    AUTO_SS = "AUTOSS"
    SCREENSHARE_DONTLOG = "SCREENSHAREDONTLOG"
    AUTOSS_SUCCESS = "AUTOSS_SUCCESS"
    AUTOSS_ERROR = "AUTOSS_ERROR"
    SCREENSHAREDONTLOG_SUCCESS = "SCREENSHAREDONTLOG_SUCCESS"
    SCREENSHAREDONTLOG_ERROR = "SCREENSHAREDONTLOG_ERROR"
    
    
    PING = "PING"
    PONG = "PONG"
    
    
    QUEUE_JOIN_SUCCESS = "QUEUE_JOIN_SUCCESS"
    QUEUE_JOIN_ERROR = "QUEUE_JOIN_ERROR"


class MessageSchemas:
    
    WARP_PLAYERS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "WARP_PLAYERS"},
            "game_id": {"type": "string"},
            "map": {"type": "string"},
            "is_ranked": {"type": "boolean"},
            "team1": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ign": {"type": "string"}
                    },
                    "required": ["ign"]
                }
            },
            "team2": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "ign": {"type": "string"}
                    },
                    "required": ["ign"]
                }
            }
        },
        "required": ["type", "game_id", "map", "is_ranked", "team1", "team2"]
    }
    
    SCORING = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "SCORING"},
            "gameid": {"type": "string"},
            "winningTeamNumber": {"type": "integer", "minimum": 1, "maximum": 2},
            "mvps": {
                "type": "array",
                "items": {"type": "string"}
            },
            "bedsbroken": {
                "type": "array",
                "items": {"type": "string"}
            },
            "players": {
                "type": "object",
                "patternProperties": {
                    ".*": {
                        "type": "object",
                        "properties": {
                            "kills": {"type": "integer", "minimum": 0},
                            "deaths": {"type": "integer", "minimum": 0},
                            "bedbroken": {"type": "boolean"},
                            "finalkills": {"type": "integer", "minimum": 0},
                            "diamonds": {"type": "integer", "minimum": 0},
                            "irons": {"type": "integer", "minimum": 0},
                            "gold": {"type": "integer", "minimum": 0},
                            "emeralds": {"type": "integer", "minimum": 0},
                            "blocksplaced": {"type": "integer", "minimum": 0}
                        },
                        "required": ["kills", "deaths", "bedbroken", "finalkills", 
                                   "diamonds", "irons", "gold", "emeralds", "blocksplaced"]
                    }
                }
            }
        },
        "required": ["type", "gameid", "winningTeamNumber", "players"]
    }
    
    CHECK_PLAYER = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "CHECK_PLAYER"},
            "ign": {"type": "string"},
            "request_id": {"type": "string"}
        },
        "required": ["type", "ign", "request_id"]
    }
    
    PLAYER_STATUS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "PLAYER_STATUS"},
            "ign": {"type": "string"},
            "online": {"type": "boolean"},
            "request_id": {"type": "string"}
        },
        "required": ["type", "ign", "online", "request_id"]
    }
    
    QUEUE_FROM_INGAME = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "QUEUEFROMINGAME"},
            "ign": {"type": "string"},
            "queue_type": {"type": "string"}
        },
        "required": ["type", "ign", "queue_type"]
    }
    
    PING = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "PING"}
        },
        "required": ["type"]
    }
    
    PONG = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "PONG"}
        },
        "required": ["type"]
    }
    
    VOIDING = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "VOIDING"},
            "gameid": {"type": "string"},
            "reason": {"type": "string"}
        },
        "required": ["type", "gameid"]
    }
    
    CALL_CMD = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "CALL_CMD"},
            "requester_ign": {"type": "string"},
            "target_ign": {"type": "string"}
        },
        "required": ["type", "requester_ign", "target_ign"]
    }
    
    CALL_SUCCESS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "CALL_SUCCESS"},
            "requester_ign": {"type": "string"},
            "target_ign": {"type": "string"}
        },
        "required": ["type", "requester_ign", "target_ign"]
    }
    
    CALL_FAILURE = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "CALL_FAILURE"},
            "requester_ign": {"type": "string"},
            "target_ign": {"type": "string"},
            "reason": {"type": "string"}
        },
        "required": ["type", "requester_ign", "target_ign", "reason"]
    }
    
    AUTO_SS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "AUTOSS"},
            "target_ign": {"type": "string"},
            "requester_ign": {"type": "string"}
        },
        "required": ["type", "target_ign", "requester_ign"]
    }
    
    SCREENSHARE_DONTLOG = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "SCREENSHAREDONTLOG"},
            "target_ign": {"type": "string"},
            "enabled": {"type": "boolean"}
        },
        "required": ["type", "target_ign", "enabled"]
    }
    
    WARP_SUCCESS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "WARP_SUCCESS"},
            "game_id": {"type": "string"},
            "map": {"type": "string"}
        },
        "required": ["type", "game_id", "map"]
    }
    
    WARP_FAILED_ARENA = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "WARP_FAILED_ARENA_NOT_FOUND"},
            "game_id": {"type": "string"},
            "map": {"type": "string"}
        },
        "required": ["type", "game_id", "map"]
    }
    
    WARP_FAILED_OFFLINE = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "WARP_FAILED_OFFLINE_PLAYERS"},
            "game_id": {"type": "string"},
            "offline_players": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["type", "game_id", "offline_players"]
    }
    
    RETRY_GAME = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "RETRYGAME"},
            "game_id": {"type": "string"}
        },
        "required": ["type", "game_id"]
    }

    # Accepts either game_id or gameid to be lenient with client payloads
    AUTO_RETRY_FROM_INGAME = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "AUTORETRYGAMEFROMINGAME"},
            "game_id": {"type": "string"},
            "gameid": {"type": "string"}
        },
        "oneOf": [
            {"required": ["type", "game_id"]},
            {"required": ["type", "gameid"]}
        ]
    }
    
    QUEUE_STATUS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "QUEUESTATUS"},
            "queues": {
                "type": "object",
                "patternProperties": {
                    ".*": {
                        "type": "object",
                        "properties": {
                            "players": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "elo_range": {
                                "type": "object",
                                "properties": {
                                    "min": {"type": "integer"},
                                    "max": {"type": "integer"}
                                },
                                "required": ["min", "max"]
                            },
                            "capacity": {"type": "integer", "minimum": 1}
                        },
                        "required": ["players", "elo_range", "capacity"]
                    }
                }
            }
        },
        "required": ["type", "queues"]
    }
    
    VERIFICATION = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "VERIFICATION"},
            "ign": {"type": "string"},
            "discord_id": {"type": "string"},
            "verified": {"type": "boolean"}
        },
        "required": ["type", "ign", "discord_id", "verified"]
    }
    
    QUEUE_JOIN_SUCCESS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "QUEUE_JOIN_SUCCESS"},
            "ign": {"type": "string"},
            "queue_type": {"type": "string"},
            "channel_id": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["type", "ign", "queue_type", "channel_id", "message"]
    }
    
    QUEUE_JOIN_ERROR = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "QUEUE_JOIN_ERROR"},
            "error": {"type": "string"}
        },
        "required": ["type", "error"]
    }
    
    AUTOSS_SUCCESS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "AUTOSS_SUCCESS"},
            "target_ign": {"type": "string"},
            "requester_ign": {"type": "string"},
            "screenshare_id": {"type": "string"},
            "message": {"type": "string"}
        },
        "required": ["type", "target_ign", "requester_ign", "screenshare_id", "message"]
    }
    
    AUTOSS_ERROR = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "AUTOSS_ERROR"},
            "error": {"type": "string"},
            "target_ign": {"type": "string"},
            "requester_ign": {"type": "string"}
        },
        "required": ["type", "error", "target_ign", "requester_ign"]
    }
    
    SCREENSHAREDONTLOG_SUCCESS = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "SCREENSHAREDONTLOG_SUCCESS"},
            "target_ign": {"type": "string"},
            "enabled": {"type": "boolean"},
            "message": {"type": "string"}
        },
        "required": ["type", "target_ign", "enabled", "message"]
    }
    
    SCREENSHAREDONTLOG_ERROR = {
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "SCREENSHAREDONTLOG_ERROR"},
            "error": {"type": "string"},
            "target_ign": {"type": "string"}
        },
        "required": ["type", "error", "target_ign"]
    }


class MessageParsingError(Exception):
    def __init__(self, message: str, original_data: str = None, validation_error: Exception = None):
        self.message = message
        self.original_data = original_data
        self.validation_error = validation_error
        super().__init__(self.message)


class MessageValidator:
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.schemas = {
            MessageType.WARP_PLAYERS: MessageSchemas.WARP_PLAYERS,
            MessageType.SCORING: MessageSchemas.SCORING,
            MessageType.CHECK_PLAYER: MessageSchemas.CHECK_PLAYER,
            MessageType.PLAYER_STATUS: MessageSchemas.PLAYER_STATUS,
            MessageType.QUEUE_FROM_INGAME: MessageSchemas.QUEUE_FROM_INGAME,
            MessageType.PING: MessageSchemas.PING,
            MessageType.PONG: MessageSchemas.PONG,
            MessageType.VOIDING: MessageSchemas.VOIDING,
            MessageType.CALL_CMD: MessageSchemas.CALL_CMD,
            MessageType.CALL_SUCCESS: MessageSchemas.CALL_SUCCESS,
            MessageType.CALL_FAILURE: MessageSchemas.CALL_FAILURE,
            MessageType.AUTO_SS: MessageSchemas.AUTO_SS,
            MessageType.SCREENSHARE_DONTLOG: MessageSchemas.SCREENSHARE_DONTLOG,
            MessageType.WARP_SUCCESS: MessageSchemas.WARP_SUCCESS,
            MessageType.WARP_FAILED_ARENA: MessageSchemas.WARP_FAILED_ARENA,
            MessageType.WARP_FAILED_OFFLINE: MessageSchemas.WARP_FAILED_OFFLINE,
            MessageType.RETRY_GAME: MessageSchemas.RETRY_GAME,
            MessageType.AUTO_RETRY_FROM_INGAME: MessageSchemas.AUTO_RETRY_FROM_INGAME,
            MessageType.QUEUE_STATUS: MessageSchemas.QUEUE_STATUS,
            MessageType.VERIFICATION: MessageSchemas.VERIFICATION,
            MessageType.QUEUE_JOIN_SUCCESS: MessageSchemas.QUEUE_JOIN_SUCCESS,
            MessageType.QUEUE_JOIN_ERROR: MessageSchemas.QUEUE_JOIN_ERROR,
            MessageType.AUTOSS_SUCCESS: MessageSchemas.AUTOSS_SUCCESS,
            MessageType.AUTOSS_ERROR: MessageSchemas.AUTOSS_ERROR,
            MessageType.SCREENSHAREDONTLOG_SUCCESS: MessageSchemas.SCREENSHAREDONTLOG_SUCCESS,
            MessageType.SCREENSHAREDONTLOG_ERROR: MessageSchemas.SCREENSHAREDONTLOG_ERROR,
        }
    
    def parse_message(self, raw_data: Union[str, bytes]) -> Dict[str, Any]:
        try:
            if isinstance(raw_data, bytes):
                raw_data = raw_data.decode('utf-8')
            
            if not raw_data.strip():
                raise MessageParsingError("Empty message received", raw_data)
            
            message = json.loads(raw_data)
            
            if not isinstance(message, dict):
                raise MessageParsingError("Message must be a JSON object", raw_data)
            
            return message
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing failed: {e}")
            raise MessageParsingError(f"Invalid JSON format: {e}", raw_data, e)
        except UnicodeDecodeError as e:
            self.logger.error(f"Unicode decoding failed: {e}")
            raise MessageParsingError(f"Invalid UTF-8 encoding: {e}", raw_data, e)
        except Exception as e:
            self.logger.error(f"Unexpected error during message parsing: {e}")
            raise MessageParsingError(f"Unexpected parsing error: {e}", raw_data, e)
    
    def validate_message(self, message: Dict[str, Any]) -> bool:
        try:
            message_type = message.get('type')
            
            if not message_type:
                raise MessageParsingError("Message missing required 'type' field", str(message))
            
            if message_type not in self.schemas:
                raise MessageParsingError(f"Unknown message type: {message_type}", str(message))
            
            schema = self.schemas[message_type]
            validate(instance=message, schema=schema, cls=Draft7Validator)
            
            return True
            
        except ValidationError as e:
            self.logger.error(f"Message validation failed: {e.message}")
            raise MessageParsingError(f"Validation error: {e.message}", str(message), e)
        except Exception as e:
            self.logger.error(f"Unexpected error during message validation: {e}")
            raise MessageParsingError(f"Unexpected validation error: {e}", str(message), e)
    
    def parse_and_validate(self, raw_data: Union[str, bytes]) -> Dict[str, Any]:
        message = self.parse_message(raw_data)
        self.validate_message(message)
        return message
    
    def is_valid_message_type(self, message_type: str) -> bool:
        return message_type in self.schemas
    
    def get_schema(self, message_type: str) -> Optional[Dict[str, Any]]:
        return self.schemas.get(message_type)
    
    def get_supported_message_types(self) -> list:
        return list(self.schemas.keys())


class MessageBuilder:
    
    @staticmethod
    def build_warp_players(game_id: str, map_name: str, is_ranked: bool, team1: list, team2: list) -> Dict[str, Any]:
        return {
            "type": MessageType.WARP_PLAYERS,
            "game_id": game_id,
            "map": map_name,
            "is_ranked": is_ranked,
            "team1": team1,
            "team2": team2
        }
    
    @staticmethod
    def build_check_player(ign: str, request_id: str) -> Dict[str, Any]:
        return {
            "type": MessageType.CHECK_PLAYER,
            "ign": ign,
            "request_id": request_id
        }
    
    @staticmethod
    def build_player_status(ign: str, online: bool, request_id: str) -> Dict[str, Any]:
        return {
            "type": MessageType.PLAYER_STATUS,
            "ign": ign,
            "online": online,
            "request_id": request_id
        }
    
    @staticmethod
    def build_queue_status(queues: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": MessageType.QUEUE_STATUS,
            "queues": queues
        }
    
    @staticmethod
    def build_ping() -> Dict[str, Any]:
        return {
            "type": MessageType.PING
        }
    
    @staticmethod
    def build_pong() -> Dict[str, Any]:
        return {
            "type": MessageType.PONG
        }
    
    @staticmethod
    def build_warp_success(game_id: str, map_name: str = None) -> Dict[str, Any]:
        return {
            "type": MessageType.WARP_SUCCESS,
            "game_id": game_id,
            "map": map_name or "unknown"
        }
    
    @staticmethod
    def build_warp_failed_arena(game_id: str, map_name: str) -> Dict[str, Any]:
        return {
            "type": MessageType.WARP_FAILED_ARENA,
            "game_id": game_id,
            "map": map_name
        }
    
    @staticmethod
    def build_warp_failed_offline(game_id: str, offline_players: list) -> Dict[str, Any]:
        return {
            "type": MessageType.WARP_FAILED_OFFLINE,
            "game_id": game_id,
            "offline_players": offline_players
        }
    
    @staticmethod
    def build_call_success(requester_ign: str, target_ign: str) -> Dict[str, Any]:
        return {
            "type": MessageType.CALL_SUCCESS,
            "requester_ign": requester_ign,
            "target_ign": target_ign
        }
    
    @staticmethod
    def build_call_failure(requester_ign: str, target_ign: str, reason: str) -> Dict[str, Any]:
        return {
            "type": MessageType.CALL_FAILURE,
            "requester_ign": requester_ign,
            "target_ign": target_ign,
            "reason": reason
        }
