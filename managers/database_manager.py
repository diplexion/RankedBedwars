import logging
from pymongo import MongoClient, errors
from typing import Optional, Dict, Any
import yaml
import os
import bson
import threading
from urllib.parse import quote_plus
from datetime import datetime



class DatabaseManager:
    _instance = None
    _initialized = False
    _lock = threading.Lock()

    def __new__(cls, config_path: str = 'configs/config.yml'):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = 'configs/config.yml'):
        if not DatabaseManager._initialized:
            logging.getLogger('pymongo').setLevel(logging.WARNING)
            self.client: Optional[MongoClient] = None
            self.db = None
            self._is_connected = False
            self.config = self._load_yaml_config(config_path)
            self._connect_and_init_db()
            DatabaseManager._initialized = True

    def ensure_connection(self):
        if not self._is_connected or self.client is None:
            self._connect_and_init_db()
            return

        try:
            
            self.client.admin.command('ping')
        except Exception:
            self._connect_and_init_db()

    def _load_yaml_config(self, config_path: str) -> dict:
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logging.error(f"Failed to load config file {config_path}: {e}")
            raise

    def _connect_and_init_db(self):
        with self._lock:
            
            if self.client is not None:
                try:
                    
                    self.client.admin.command('ping')
                    self._is_connected = True
                    return
                except Exception as e:
                    
                    try:
                        self.client.close()
                    except Exception:
                        pass
                    self.client = None
                    self._is_connected = False
                
            max_retries = 3
            retry_delay = 1  
            
            for attempt in range(max_retries):
                try:
                    db_cfg = self.config.get('database', {})
                    bot_cfg = self.config.get('bot', {})
                    username = quote_plus(db_cfg.get('username', 'deyo'))
                    password = quote_plus(db_cfg.get('password', 'riz2005'))
                    host = db_cfg.get('host', 'egirl.deyo.lol')
                    port = str(db_cfg.get('port', 27017))
                    db_name = db_cfg.get('db_name', 'ranked_bedwars')
                    self.db_name = db_name
                    
                    uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource=admin"
                    self.client = MongoClient(
                        uri,
                        serverSelectionTimeoutMS=5000,
                        connectTimeoutMS=5000,
                        socketTimeoutMS=5000,
                        maxPoolSize=50,
                        retryWrites=True
                    )
                    
                    
                    self.client.admin.command('ping')
                    self.db = self.client[self.db_name]
                    self._ensure_collections()
                    self._is_connected = True
                    return
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.warning(f"MongoDB connection attempt {attempt + 1} failed: {e}. Retrying in {retry_delay} seconds...")
                        import time
                        time.sleep(retry_delay)
                        retry_delay *= 2  
                    else:
                        logging.error(f"Failed to connect to MongoDB after {max_retries} attempts: {e}")
                        self._is_connected = False
                        raise



    def reset_daily_elo(self):
        result = self.db['users'].update_many({}, {'$set': {'dailyelo': 0}})
        logging.info(f"Reset daily elo for {result.modified_count} users.")


    def reset_recent_games(self):
        result = self.db['recentgames'].delete_many({})
        logging.info(f"Wiped {result.deleted_count} recent games.")

    def _ensure_collections(self) -> None:
        
        
        if 'users' not in self.db.list_collection_names():
            self.db.create_collection('users', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['discordid', 'ign'],
                    'properties': {
                        'discordid': {'bsonType': 'string'},
                        'ign': {'bsonType': 'string'},
                        'exp': {'bsonType': 'int'},
                        'totalexp': {'bsonType': 'int'},
                        'level': {'bsonType': 'int'},
                        'elo': {'bsonType': 'int'},
                        'dailyelo': {'bsonType': 'int'},  
                        'wins': {'bsonType': 'int'},
                        'losses': {'bsonType': 'int'},
                        'winstreak': {'bsonType': 'int'},
                        'loosestreak': {'bsonType': 'int'},
                        'highest_elo': {'bsonType': 'int'},
                        'highstwinstreak': {'bsonType': 'int'},
                        'bedsbroken': {'bsonType': 'int'},
                        'mvps': {'bsonType': 'int'},
                        'ss': {'bsonType': 'int'},
                        'scored': {'bsonType': 'int'},
                        'voided': {'bsonType': 'int'},
                        'gamesplayed': {'bsonType': 'int'},
                        'finalkills': {'bsonType': 'int'},
                        'kills': {'bsonType': 'int'},
                        'deaths': {'bsonType': 'int'},
                        'diamonds': {'bsonType': 'int'},
                        'irons': {'bsonType': 'int'},
                        'gold': {'bsonType': 'int'},
                        'emeralds': {'bsonType': 'int'},
                        'blocksplaced': {'bsonType': 'int'},
                        'banned': {'bsonType': 'bool'},
                        'ban_reason': {'bsonType': 'string'},
                        'ban_date': {'bsonType': 'timestamp'},
                        'ban_expiry': {'bsonType': 'timestamp'},
                        'ban_staff': {'bsonType': 'string'},
                        'last_unban_reason': {'bsonType': 'string'},
                        'last_unbanned_by': {'bsonType': 'string'},
                        'last_unban_date': {'bsonType': 'timestamp'},
                        'partyingnorelist':  {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'strikes_count': {'bsonType': 'int'},
                        'latest_strike_date': {'bsonType': 'timestamp'},
                        'latest_strike_reason': {'bsonType': 'string'},
                        'latest_strike_staff': {'bsonType': 'string'},
                    }
                }
            })
            
            
            self.db['users'].create_index([
                ('banned', 1),
                ('ban_expiry', 1)
            ], name='banned_expiry_idx')

            
            self.db['users'].create_index([
                ('strikes_count', 1),
                ('latest_strike_date', 1)
            ], name='strikes_idx')

        if 'elos' not in self.db.list_collection_names():
            self.db.create_collection('elos', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['roleid', 'minelo', 'maxelo', 'winelo', 'loselo', 'mvpelo', 'color', 'rankname'],
                    'properties': {
                        'roleid': {'bsonType': 'string'},
                        'minelo': {'bsonType': 'int'},
                        'maxelo': {'bsonType': 'int'},
                        'winelo': {'bsonType': 'int'},
                        'loselo': {'bsonType': 'int'},
                        'mvpelo': {'bsonType': 'int'},
                        'color': {'bsonType': 'string'},
                        'rankname': {'bsonType': 'string'}
                    }
                }
            })

        if 'games' not in self.db.list_collection_names():
            self.db.create_collection('games', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['gameid','team1', 'team2','gametype'],
                    'properties': {
                        'id': {'bsonType':'string'},
                        'gameid': {'bsonType':'string'},
                        'team1': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'team2': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'winningteam': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'loosingteam': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'mvps': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'bedbreakers': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'state': {'bsonType': 'string', 'enum': ['pending', 'voided', 'scored', 'unknown','submitted']},
                        'gametype': {'bsonType': 'string'},
                        'date': {'bsonType': 'timestamp'},
                        'start_time': {'bsonType': 'timestamp'},
                        'end_time': {'bsonType': 'timestamp'}
                    }
                }
            })


        if 'screenshares' not in self.db.list_collection_names():
            self.db.create_collection('screenshares', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['id'],
                    'properties': {
                        'id': {'bsonType':'string'},
                        'target_id': {'bsonType': 'string'},
                        'requester_id': {'bsonType': 'string'},
                        'screensharer_id': {'bsonType': 'string'},
                        'reason': {'bsonType': 'string'},
                        'evidence_url': {'bsonType': 'string'},
                        'state': {'bsonType': 'string', 'enum': ['pending', 'in_progress', 'completed']},
                        'start_time': {'bsonType': 'timestamp'},
                        'end_time': {'bsonType': 'timestamp'},
                        'is_frozen': {'bsonType': 'bool'},
                        'channel_id': {'bsonType': 'string'},
                        'result': {'bsonType': 'string'},
                        'result_evidence_url': {'bsonType': 'string'},
                        'created_at': {'bsonType': 'timestamp'},
                        'updated_at': {'bsonType': 'timestamp'}
                    }
                }
            })

        if 'recentgames' not in self.db.list_collection_names():
            self.db.create_collection('recentgames', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['result','discordid', 'gametype', 'gameid'],
                    'properties': {
                        'id': {'bsonType':'string'},
                        'discordid': {'bsonType': 'string'},
                        'gameid': {'bsonType': 'string'},
                        'result': {'bsonType': 'string', 'enum': ['win', 'lose','voided', 'pending', 'unknown','submitted']},
                        'state': {'bsonType': 'string', 'enum': ['pending', 'voided', 'scored', 'unknown', 'submitted']},
                        'ismvp': {'bsonType': 'bool'},
                        'gametype': {'bsonType': 'string'},
                        'date': {'bsonType': 'timestamp'},
                        'elochange': {'bsonType': 'int'},
                        'bedbroke': {'bsonType': 'bool'},
                        'kills': {'bsonType': 'string'},
                        'deaths': {'bsonType': 'string'},
                        'finalkills': {'bsonType': 'int'},
                        'diamonds': {'bsonType': 'int'},
                        'irons': {'bsonType': 'int'},
                        'gold': {'bsonType': 'int'},
                        'emeralds': {'bsonType': 'int'},
                        'blocksplaced': {'bsonType': 'int'}
                    }
                }
            })
        if 'queues' not in self.db.list_collection_names():
            self.db.create_collection('queues', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                   'required': ['channelid', 'maxplayers', 'minelo', 'maxelo', 'iscasual'],  
                    'properties': {
                        'channelid': {'bsonType': 'string'},
                        'maxplayers': {'bsonType': 'int'},
                        'minelo': {'bsonType': 'int'},
                        'maxelo': {'bsonType': 'int'},
                        'iscasual': {'bsonType': 'bool'}
                       }
                }
            })

        if 'settings' not in self.db.list_collection_names():
            self.db.create_collection('settings', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['discordid'],
                    'properties': {
                        'discordid': {'bsonType': 'string'},
                        'isprefixtoggled': {'bsonType': 'bool'},
                       'ispartyinvitestoggled': {'bsonType': 'bool'},
                       'isscoringpingtoggled': {'bsonType': 'bool'},
                       'nickname': {'bsonType': 'string'},
                       'skinpose': {'bsonType':'string'},
                       'staticnickname': {'bsonType':'bool'},
                       'ownedthemes': {'bsonType': 'array', 'items': {'bsonType':'string'}},
                       'theme': {'bsonType':'string'},

                      }
                }
            })

        if 'queuestats' not in self.db.list_collection_names():
            self.db.create_collection('queuestats', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                  'required': ['queuetype', 'stats',],  
                    'properties': {
                        'queuetype': {'bsonType': 'string'},
                       'stats': {'bsonType': 'bool'},
                      }
                }
            })

        if 'punishments' not in self.db.list_collection_names():
            self.db.create_collection('punishments', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['discordid', 'ign', 'punishment', 'reason', 'date'],
                    'properties': {
                        'discordid': {'bsonType': 'string'},
                        'ign': {'bsonType': 'string'},
                        'punishment': {'bsonType': 'string'},
                       'reason': {'bsonType': 'string'},
                        'date': {'bsonType': 'timestamp'},
                        'duration': {'bsonType': 'timestamp'},
                       }
                }
            })

        if 'gameschannels' not in self.db.list_collection_names():
            self.db.create_collection('gameschannels', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['gameid'],
                    'properties': {
                        'id': {'bsonType':'string'},
                       'gameid': {'bsonType': 'string'},
                       'textchannelid': {'bsonType': 'string'},
                       'team1voicechannelid': {'bsonType': 'string'},
                       'team2voicechannelid': {'bsonType': 'string'},
                       'pickingvoicechannelid': {'bsonType': 'string'},
                       }
                }
            })

        if 'bans' not in self.db.list_collection_names():
            self.db.create_collection('bans', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['discordid', 'ign', 'reason', 'date', 'duration', 'unbanned'],
                    'properties': {
                        'discordid': {'bsonType':'string'},
                        'ign': {'bsonType':'string'},
                        'reason': {'bsonType':'string'},
                        'date': {'bsonType': 'timestamp'},
                        'duration': {'bsonType': 'timestamp'},
                        'staffid': {'bsonType':'string'},
                        'unbanned': {'bsonType': 'bool'},
                        'unbanreason': {'bsonType':'string'},
                        'unbannedby': {'bsonType':'string'},
                        'unbannedate': {'bsonType': 'timestamp'},
                        }
                }  
            })

        if 'mutes' not in self.db.list_collection_names():
            self.db.create_collection('mutes', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['discordid', 'ign', 'reason', 'date', 'duration', 'staffid', 'unmuted'],
                    'properties': {
                        'discordid': {'bsonType':'string'},
                        'ign': {'bsonType':'string'},
                        'reason': {'bsonType':'string'},
                        'date': {'bsonType': 'timestamp'},
                        'duration': {'bsonType': 'timestamp'},
                        'staffid': {'bsonType':'string'},
                        'unmuted': {'bsonType': 'bool'},
                        'unmutereason': {'bsonType':'string'},
                        'unmutedby': {'bsonType':'string'},
                        'unmutedate': {'bsonType': 'timestamp'},
                    }
                }
            })
        if 'booster' not in self.db.list_collection_names():
            self.db.create_collection('booster', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                    'required': ['multiplier'],
                    'properties': {
                        'multiplier': {'bsonType':'string'},
                    }
                }
            })
            

        if 'strikes' not in self.db.list_collection_names():
            self.db.create_collection('strikes', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                   'required': ['discordid','staffid', 'ign','reason', 'date'],
                    'properties': {
                        'discordid': {'bsonType':'string'},
                        'staffid': {'bsonType': 'string'},
                        'ign': {'bsonType':'string'},
                        'reason': {'bsonType':'string'},
                        'date': {'bsonType': 'timestamp'},  
                    }
                }
            })

        if 'guilds' not in self.db.list_collection_names():
            self.db.create_collection('guilds', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                   'required': ['guildid'],  
                    'properties': {
                        'guildid': {'bsonType':'string'},
                        'guildname': {'bsonType':'string'},
                        'guildtag': {'bsonType':'string'},
                        'ownerid': {'bsonType':'string'},
                        'ownerign': {'bsonType':'string'},
                        'adminsid': {'bsonType': 'array', 'items': {'bsonType':'string'}},
                        'adminsign': {'bsonType': 'array', 'items': {'bsonType':'string'}},
                        'moderatorsid': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'moderatorsign': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'membersid': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'membersign': {'bsonType': 'array', 'items': {'bsonType': 'string'}},
                        'level': {'bsonType': 'int'},
                        'exp': {'bsonType': 'int'},
                        'totalexp': {'bsonType': 'int'},
                        'totalelo': {'bsonType': 'int'},
                        'gvgsplayed': {'bsonType': 'int'},
                        'gvgwins': {'bsonType': 'int'},
                        'gvglosses': {'bsonType': 'int'},
                        'ownedsysmbols': {'bsonType': 'array', 'items': {'bsonType':'string'}},
                        'ownedcolors': {'bsonType': 'array', 'items': {'bsonType':'string'}},
                    }
                }
            })
        if 'counters' not in self.db.list_collection_names():
            self.db.create_collection('counters', validator={
                '$jsonSchema': {
                    'bsonType': 'object',
                   'required': ['_id', 'seq'],
                    'properties': {
                        '_id': {'bsonType':'string'},
                        'seq': {'bsonType': 'int'},
                    }
                }
            })
            for counter in ['gameid', 'recentgames', 'screenshareid', 'banid', 'muteid', 'strikeid', 'punishmentid', 'gameschannels']:
                self.db['counters'].insert_one({'_id': counter, 'seq': 0})
            

        
        
        
        
        
        
        
            

    def insert(self, collection_name: str, document: Dict[str, Any]) -> Any:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            
            if collection_name in ['banid', 'muteid', 'screenshareid', 'strikeid', 'punishmentid', 'gameschannels', 'gamesid', 'recentgames']:
                if '_id' not in document:
                    document['_id'] = str(self.get_next_sequence(collection_name))
                for field in ['date', 'duration', 'unbannedate', 'unmutedate']:
                    if field in document and isinstance(document[field], (int, float)):
                        document[field] = bson.timestamp.Timestamp(document[field], 0)
            result = collection.insert_one(document)
            logging.debug(f"Inserted document into {collection_name}: {document}")
            return result.inserted_id
        except Exception as e:
            logging.error(f"Error in insert operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def find(self, collection_name: str, query: Dict[str, Any], limit: int = None) -> list[Dict[str, Any]]:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            cursor = collection.find(query)
            if limit is not None:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            logging.error(f"Error in find operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def find_one(self, collection_name: str, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            return collection.find_one(query)
        except Exception as e:
            logging.error(f"Error in find_one operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def close(self) -> None:
        if self.client:
            self.client.close()
            logging.info("Closed MongoDB connection.")


    def update_player_setting(self, discord_id: str, setting: str, value: Any) -> bool:
        self.ensure_connection()
        try:
            collection = self.db['settings']
            update_result = collection.update_one(
                {"discordid": str(discord_id)},
                {"$set": {setting: value}},
                upsert=True
            )
            return update_result.modified_count > 0 or update_result.upserted_id is not None
        except Exception as e:
            logging.error(f"Error in update_player_setting operation for player {discord_id}: {e}")
            self.ensure_connection()  
            raise


    def delete(self, collection_name: str, query: Dict[str, Any]) -> bool:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            result = collection.delete_one(query)
            logging.debug(f"Deleted from {collection_name} where {query}, deleted_count={result.deleted_count}")
            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"Error in delete operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def increment(self, collection_name: str, filter_query: Dict[str, Any], update_query: Dict[str, Any]) -> bool:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            result = collection.update_one(filter_query, update_query)
            logging.debug(f"Incremented in {collection_name} where {filter_query} with {update_query}, modified_count={result.modified_count}")
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"Error in increment operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def get_next_sequence(self, name: str) -> int:
        self.ensure_connection()
        try:
            counter = self.db['counters'].find_one_and_update(
                {'_id': name},
                {'$inc': {'seq': 1}},
                return_document=True
            )
            if counter is None:
                raise ValueError(f"Counter for {name} not found.")
            return counter['seq']
        except Exception as e:
            logging.error(f"Error in get_next_sequence operation for {name}: {e}")
            self.ensure_connection()  
            raise


    def update_one(self, collection_name: str, filter_query: Dict[str, Any], update_query: Dict[str, Any], upsert: bool = False) -> bool:
        self.ensure_connection()
        try:
            collection = self.db[collection_name]
            result = collection.update_one(filter_query, update_query, upsert=upsert)
            logging.debug(f"Updated one in {collection_name} where {filter_query} with {update_query}, modified_count={result.modified_count}")
            return result.modified_count > 0 or (upsert and result.upserted_id is not None)
        except Exception as e:
            logging.error(f"Error in update_one operation on {collection_name}: {e}")
            self.ensure_connection()  
            raise


    def calculate_mvp_rate(self, mvps: int, games_played: int) -> int:
        if games_played == 0:
            return 0
        return int((mvps / games_played) * 100)


    def calculate_rating(self, wins: int, losses: int) -> int:
        total_games = wins + losses
        if total_games == 0:
            return 0
        return int((wins / total_games) * 1000)


    def update_user_games(self, user_id: str, game_id: str, result: str, is_mvp: bool):
        self.ensure_connection()
        try:
            update_result = self.db['users'].update_one(
                {'discordid': str(user_id)},
                {
                    '$inc': {'gamesplayed': 1},
                    '$push': {
                        'recentgames': {
                            '$each': [{'gameid': game_id, 'result': result, 'ismvp': is_mvp, 'date': datetime.now()}],
                            '$slice': -10
                        }
                    }
                }
            )
            logging.debug(f"Updated user {user_id} games: {update_result.modified_count}")
        except Exception as e:
            logging.error(f"Error in update_user_games operation for user {user_id}: {e}")
            self.ensure_connection()  
            raise
        

    def update_player_ign(self, discord_id: str, old_ign: str, new_ign: str) -> bool:
        updated = False
        user_result = self.db['users'].update_one(
            {'discordid': str(discord_id)},
            {'$set': {'ign': new_ign}}
        )
        updated = updated or user_result.modified_count > 0
        owner_result = self.db['guilds'].update_one(
            {'ownerid': str(discord_id)},
            {'$set': {'ownerign': new_ign}}
        )
        updated = updated or owner_result.modified_count > 0
        admin_result = self.db['guilds'].update_many(
            {'adminsid': str(discord_id)},
            {'$set': {'adminsign.$[elem]': new_ign}},
            array_filters=[{'elem': old_ign}]
        )
        updated = updated or admin_result.modified_count > 0
        mod_result = self.db['guilds'].update_many(
            {'moderatorsid': str(discord_id)},
            {'$set': {'moderatorsign.$[elem]': new_ign}},
            array_filters=[{'elem': old_ign}]
        )
        updated = updated or mod_result.modified_count > 0
        member_result = self.db['guilds'].update_many(
            {'membersid': str(discord_id)},
            {'$set': {'membersign.$[elem]': new_ign}},
            array_filters=[{'elem': old_ign}]
        )
        updated = updated or member_result.modified_count > 0
        logging.info(f"Updated IGN for player {discord_id} from '{old_ign}' to '{new_ign}' across all collections")
        return updated


    def delete_elo_roles(self) -> list[str]:
        try:
            elo_roles = self.db['elos'].find({}, {'roleid': 1})
            role_ids = [role['roleid'] for role in elo_roles]
            self.db['elos'].delete_many({})
            logging.info(f"Deleted all ELO roles, returned {len(role_ids)} role IDs.")
            return role_ids
        except Exception as e:
            logging.error(f"Failed to delete ELO roles: {e}")
            return []


    def auto_disband_inactive_parties(self, inactive_seconds: int = 7200) -> int:
        current_time = int(datetime.now().timestamp())
        cutoff_time = current_time - inactive_seconds
        inactive_parties = self.find('parties', {'last_activity': {'$lt': cutoff_time}})
        count = 0
        for party in inactive_parties:
            party_name = party.get('party_name')
            if party_name:
                try:
                    self.delete('parties', {'party_name': party_name})
                    count += 1
                except Exception as e:
                    logging.error(f"Failed to auto-disband party {party_name}: {e}")
        logging.info(f"Auto-disbanded {count} inactive parties.")
        return count
