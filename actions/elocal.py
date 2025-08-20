from managers.database_manager import DatabaseManager
from actions.fix import fix
import yaml
from datetime import datetime
import time
from bson import Timestamp

async def elocal(bot, discordid, result, ismvp, gameid, player_stats):
    db_manager = DatabaseManager()
    
    try:
        
        with open('configs/config.yml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        
        guild_id = config['bot']['guildid']
        
        user = db_manager.find_one('users', {'discordid': str(discordid)})
        if not user:
            print(f'User with discordid {discordid} not found.')
            return

        current_elo = user.get('elo', 0)
        current_exp = user.get('exp', 0)
        total_exp = user.get('totalexp', 0)
        current_level = user.get('level', 1)
        wins = user.get('wins', 0)
        losses = user.get('losses', 0)
        winstreak = user.get('winstreak', 0)
        loosestreak = user.get('loosestreak', 0)
        highstwinstreak = user.get('highstwinstreak', 0)
        current_mvp_count = user.get('mvp_count', 0)        
        rank = db_manager.find_one('elos', {'minelo': {'$lte': current_elo}, 'maxelo': {'$gte': current_elo}})
        if not rank:
            print(f'Rank not found for elo {current_elo}.')
            return

        game = db_manager.find_one('games', {'gameid': gameid})
        if not game:
            print(f'Game with gameid {gameid} not found.')
            return
            
        if game.get('state') == 'pending':
            current_timestamp = Timestamp(int(time.time()), 1)
            db_manager.db['games'].update_one(
                {'gameid': gameid},
                {'$set': {
                    'state': 'scored',
                    'end_time': current_timestamp
                }}
            )

        if game.get('gametype') == 'casual':
            db_manager.db['recentgames'].update_one(
                {'gameid': gameid, 'discordid': str(discordid)},
                {'$set': {'elochange': 0, 'result': result, 'expgain': 0}}            )
            print(f'Updated recentgames for casual game {gameid} for player {discordid}.')
            return

        elo_change = 0
        exp_gain = 0
        if result == 'win':
            elo_change += rank.get('winelo', 0)
            
            
            booster_doc = db_manager.find_one('booster', {})
            if booster_doc:
                try:
                    multiplier = float(booster_doc.get('multiplier', '1'))
                    if multiplier > 1:
                        original_elo = elo_change
                        elo_change = int(round(elo_change * multiplier))
                        print(f"Applied booster {multiplier}x: Win ELO {original_elo} → {elo_change}")
                except (ValueError, TypeError) as e:
                    print(f"Error applying booster multiplier: {e}")
            
            exp_gain += 10
        elif result == 'lose':
            elo_change += rank.get('loselo', 0)

            exp_gain += 5
            
        
        if ismvp:
            mvp_bonus = rank.get('mvpelo', 0)
            try:
                elo_change += int(mvp_bonus)
            except Exception as e:
                print(f"Error adding MVP bonus for user {discordid}: {e}")
            exp_gain += 5
            
            update_result = db_manager.db['users'].update_one(
                {'discordid': str(discordid)},
                {'$inc': {'mvps': 1}}
            )
            if update_result.modified_count == 0:
                print(f"Warning: MVP increment failed for user {discordid} (user may not exist or field missing)")
            else:
                print(f"MVP bonus applied and 'mvps' incremented for user {discordid}")

        
        elo_change = int(round(elo_change))
        exp_gain = int(round(exp_gain))
        new_elo = int(max(0, current_elo + elo_change))
        new_total_exp = int(total_exp + exp_gain)
        new_exp = int((current_exp + exp_gain) % 100)
        new_level = int(current_level + (current_exp + exp_gain) // 100)

        
        if result == 'win':
            wins += 1
            winstreak += 1
            loosestreak = 0
            if winstreak > highstwinstreak:
                highstwinstreak = winstreak
        else:
            losses += 1
            loosestreak += 1
            winstreak = 0

        
        daily_elo = int(user.get('dailyelo', 0) + elo_change)

        db_manager.db['users'].update_one(
            {'discordid': str(discordid)},
            {'$set': {
                'elo': int(round(new_elo)),
                'exp': new_exp,
                'totalexp': new_total_exp,
                'level': new_level,
                'wins': wins,
                'losses': losses,
                'winstreak': winstreak,
                'loosestreak': loosestreak,
                'highstwinstreak': highstwinstreak,
                'dailyelo': int(round(daily_elo))  
            }}
        )
        print(f'Updated elo and exp for user {discordid}: {new_elo}, {new_exp}, {new_total_exp}, {new_level}')
        await fix(bot, discordid, guild_id)

        
        if isinstance(player_stats, dict):
            stats = player_stats.get(discordid, {'kills': 0, 'deaths': 0, 'bedbroke': ismvp})
        else:
            stats = {'kills': 0, 'deaths': 0, 'bedbroke': ismvp}
        kills = stats.get('kills', 0)
        deaths = stats.get('deaths', 0)
        bedbroke = stats.get('bedbroke', ismvp)

        db_manager.db['recentgames'].update_one(
            {'gameid': gameid, 'discordid': str(discordid)},
            {'$set': {
                'elochange': elo_change,
                'state': game.get('state', 'unknown'),
                'ismvp': ismvp,
                'gametype': game.get('gametype', 'unknown'),
                'date': game.get('date', None),
                'kills': str(kills),
                'deaths': str(deaths),
                'bedbroke': bedbroke,
                'end_time': datetime.now()
            }}
        )
        print(f"Updated player stats for player {discordid} in game {gameid}: kills={kills}, deaths={deaths}, bedbroke={bedbroke}, ismvp={ismvp}")

    except Exception as e:
        print(f'Error calculating elo and exp: {e}')

    finally:
        db_manager.close()
