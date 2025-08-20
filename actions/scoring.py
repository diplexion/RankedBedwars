
import yaml
import asyncio
import discord
import os
import time
from bson import Timestamp
from managers.database_manager import DatabaseManager
from actions.elocal import elocal
from utils.discord_utils import delete_channel
from utils.embed_builder import EmbedBuilder
from actions.transcript_creator import create_transcript
from actions.scoreimage import ScoreImage

async def scoring(bot, gameid, winningteamnumber, mvp_ids, bedbreaker_ids=None, player_stats=None, iscasual=False, scoredby=None):
    db_manager = DatabaseManager()
    embed_builder = EmbedBuilder()
    try:
        with open('configs/config.yml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        guild_id = int(config['bot']['guildid'])
        exp_gain = config.get('guild', {}).get('guildwinexp', 10)

        
        scoring_log_channel = None
        try:
            scoring_log_channel_id = int(config.get('logging', {}).get('scoring'))
            scoring_log_channel = bot.get_channel(scoring_log_channel_id)
        except Exception as e:
            print(f"Could not get logging.scoring channel: {e}")

        game = db_manager.find_one('games', {'gameid': gameid})
        if not game:
            print(f'Game with gameid {gameid} not found.')
            
            if scoring_log_channel:
                embed = discord.Embed(
                    title="Scoring Attempt Failed",
                    description=f"Game with gameid `{gameid}` not found.",
                    color=discord.Color.red()
                )
                await scoring_log_channel.send(embed=embed)
            return
        if game.get('state') not in ['voided', 'pending', 'submitted']:
            print(f'Game state is not eligible for scoring: {game.get("state")})')
            
            if scoring_log_channel:
                embed = discord.Embed(
                    title="Scoring Attempt Failed",
                    description=f"Game `{gameid}` state is not eligible for scoring: `{game.get('state')}`.",
                    color=discord.Color.red()
                )
                await scoring_log_channel.send(embed=embed)
            return

        game_channels = db_manager.find_one('gameschannels', {'gameid': gameid})
        if not game_channels or 'textchannelid' not in game_channels:
            print(f"Game channels or textchannelid not found for gameid {gameid}.")
            
            if scoring_log_channel:
                embed = discord.Embed(
                    title="Scoring Attempt Failed",
                    description=f"Game channels or textchannelid not found for gameid `{gameid}`.",
                    color=discord.Color.red()
                )
                await scoring_log_channel.send(embed=embed)
            return
        
        if scoring_log_channel:
            try:
                team1_ids = game.get('team1', [])
                team2_ids = game.get('team2', [])
                mvp_ids = mvp_ids or []
                bedbreaker_ids = bedbreaker_ids or []
                scorer_mention = f'<@{scoredby}>' if scoredby else 'System'
                embed = discord.Embed(
                    title=f"Game Scored: {gameid}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Game ID", value=f"`{gameid}`", inline=True)
                embed.add_field(name="State", value=f"{game.get('state', 'unknown')}", inline=True)
                embed.add_field(name="Winning Team", value=(', '.join([f'<@{pid}>' for pid in (team1_ids if winningteamnumber == 1 else team2_ids)]) or 'None'), inline=False)
                embed.add_field(name="Losing Team", value=(', '.join([f'<@{pid}>' for pid in (team2_ids if winningteamnumber == 1 else team1_ids)]) or 'None'), inline=False)
                embed.add_field(name="MVPs", value=(', '.join([f'<@{pid}>' for pid in mvp_ids]) or 'None'), inline=False)
                embed.add_field(name="Bed Breakers", value=(', '.join([f'<@{pid}>' for pid in bedbreaker_ids]) or 'None'), inline=False)
                embed.add_field(name="Scored By", value=scorer_mention, inline=True)
                await scoring_log_channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send scoring log embed: {e}")
        text_channel_id = game_channels.get('textchannelid')
        team1_ids = game.get('team1', [])
        team2_ids = game.get('team2', [])
        winning_team = team1_ids if winningteamnumber == 1 else team2_ids
        losing_team = team2_ids if winningteamnumber == 1 else team1_ids

        
        if iscasual or game.get('gametype') == 'casual':
            db_manager.db['games'].update_one(
                {'gameid': gameid},
                {'$set': {
                    'state': 'scored',
                    'winningteam': winning_team,
                    'loosingteam': losing_team,
                    'mvps': mvp_ids,
                    'result': 'win' if winningteamnumber == 1 else 'lose'
                }}
            )
            for player_id in team1_ids + team2_ids:
                db_manager.db['recentgames'].update_one(
                    {'gameid': gameid, 'discordid': str(player_id)},
                    {'$set': {
                        'elochange': 0,
                        'result': 'win' if player_id in winning_team else 'lose',
                        'bedbroke': False
                    }}
                )
            embed_description = (
                f"Game scored\n"
                f"Since the game is a casual queue, no elo changes or win/loss updates have been detected.\n"
                f"Winning Team: {', '.join([f'<@{player_id}>' for player_id in winning_team])}\n"
                f"Losing Team: {', '.join([f'<@{player_id}>' for player_id in losing_team])}\n"
            )
            embed = embed_builder.build_success(
                title=f"Game #{gameid} Results",
                description=embed_description
            )
            scoring_channel = bot.get_channel(int(config['channels']['scoring']))
            if scoring_channel:
                await scoring_channel.send(embed=embed)
            text_channel = bot.get_channel(int(text_channel_id))
            if text_channel:
                await text_channel.send(embed=embed)
            await asyncio.sleep(30)
            try:
                waiting_vc_id = int(config['channels']['waitingvc'])
                waiting_vc = bot.get_channel(waiting_vc_id)
                for channel_id in [game_channels.get('team1voicechannelid'), game_channels.get('team2voicechannelid')]:
                    if channel_id:
                        channel = bot.get_channel(int(channel_id))
                        if channel and isinstance(channel, discord.VoiceChannel):
                            for member in channel.members:
                                await member.move_to(waiting_vc)
                if text_channel_id:
                    await delete_channel(int(text_channel_id), bot.get_guild(guild_id))
                for vc_key in ['team1voicechannelid', 'team2voicechannelid']:
                    vc_id = game_channels.get(vc_key)
                    if vc_id:
                        await delete_channel(int(vc_id), bot.get_guild(guild_id))
            except Exception as e:
                print(f'Error during channel cleanup: {e}')
            return

        
        if not mvp_ids:
            mvp_ids = []
        if bedbreaker_ids is None:
            bedbreaker_ids = []
        db_manager.db['games'].update_one(
            {'gameid': gameid},
            {'$set': {
                'state': 'scored',
                'winningteam': winning_team,
                'loosingteam': losing_team,
                'mvps': mvp_ids,
                'bedbreakers': bedbreaker_ids,
                'end_time': Timestamp(int(time.time()), 1)
            }}
        )
        all_mentions = ""
        for player_id in team1_ids + team2_ids:
            user_settings = db_manager.find_one('settings', {'discordid': str(player_id)})
            if not (user_settings and user_settings.get('isscoringpingtoggled', True)):
                all_mentions += f"<@{player_id}> "
            user = db_manager.find_one('users', {'discordid': str(player_id)})
            if user:
                result = 'win' if player_id in winning_team else 'lose'
                is_mvp = player_id in mvp_ids
                is_bedbreaker = player_id in bedbreaker_ids
                player_stats_data = {'bedbroke': is_bedbreaker}
                
                
                with open('configs/config.yml', 'r', encoding='utf-8') as file:
                    config = yaml.safe_load(file)
                    websocket_enabled = config.get('websocket', {}).get('enabled', False)
                
                if websocket_enabled and isinstance(player_stats, dict) and user.get('ign') in player_stats:
                    stats = player_stats[user.get('ign')]
                    player_stats_data = {
                        'bedbroke': bool(stats.get('bedbroke', False)) or is_bedbreaker,
                        'kills': str(stats.get('kills', 0)),
                        'deaths': str(stats.get('deaths', 0)),
                        'finalkills': int(stats.get('finalkills', 0)),
                        'diamonds': int(stats.get('diamonds', 0)),
                        'irons': int(stats.get('irons', 0)),
                        'gold': int(stats.get('gold', 0)),
                        'emeralds': int(stats.get('emeralds', 0)),
                        'blocksplaced': int(stats.get('blocksplaced', 0))
                    }
                else:
                    
                    player_stats_data = {'bedbroke': is_bedbreaker}
                recent_game_data = {
                    'discordid': str(player_id),
                    'gameid': gameid,
                    'result': result,
                    'state': 'scored',
                    'ismvp': is_mvp,
                    'gametype': game.get('gametype', 'ranked'),
                    'date': Timestamp(int(time.time()), 1),
                    'elochange': 0,
                    'bedbroke': player_stats_data['bedbroke']
                }
                
                
                if websocket_enabled and 'kills' in player_stats_data:
                    recent_game_data.update({
                        'kills': player_stats_data.get('kills', '0'),
                        'deaths': player_stats_data.get('deaths', '0'),
                        'finalkills': player_stats_data.get('finalkills', 0),
                        'diamonds': player_stats_data.get('diamonds', 0),
                        'irons': player_stats_data.get('irons', 0),
                        'gold': player_stats_data.get('gold', 0),
                        'emeralds': player_stats_data.get('emeralds', 0),
                        'blocksplaced': player_stats_data.get('blocksplaced', 0)
                    })
                db_manager.db['recentgames'].update_one(
                    {'gameid': gameid, 'discordid': str(player_id)},
                    {'$set': recent_game_data},
                    upsert=True
                )

        if scoredby is not None:
            all_mentions += f"\n Game Scored by: <@{scoredby}> "
        else:
            all_mentions += f"\n Game Automatically Scored by RBW System"

        
        for team_number, team_ids in enumerate([team1_ids, team2_ids], start=1):
            for player_id in team_ids:
                user = db_manager.find_one('users', {'discordid': str(player_id)})
                if user:
                    player_name = user.get('ign', '')
                    if isinstance(player_stats, dict):
                        stats = player_stats.get(player_name, {'bedbroke': False})
                    else:
                        stats = {'bedbroke': False}
                    
                    
                    bedsbroken = user.get('bedsbroken', 0) + (1 if stats.get('bedbroke', False) else 0)
                    update_data = {'bedsbroken': bedsbroken}
                    
                    
                    if websocket_enabled and isinstance(player_stats, dict) and player_name in player_stats:
                        advanced_stats = player_stats[player_name]
                        
                        kills = user.get('kills', 0) + int(advanced_stats.get('kills', 0))
                        deaths = user.get('deaths', 0) + int(advanced_stats.get('deaths', 0))
                        finalkills = user.get('finalkills', 0) + int(advanced_stats.get('finalkills', 0))
                        diamonds = user.get('diamonds', 0) + int(advanced_stats.get('diamonds', 0))
                        irons = user.get('irons', 0) + int(advanced_stats.get('irons', 0))
                        gold = user.get('gold', 0) + int(advanced_stats.get('gold', 0))
                        emeralds = user.get('emeralds', 0) + int(advanced_stats.get('emeralds', 0))
                        blocksplaced = user.get('blocksplaced', 0) + int(advanced_stats.get('blocksplaced', 0))
                        
                        update_data.update({
                            'kills': kills,
                            'deaths': deaths,
                            'finalkills': finalkills,
                            'diamonds': diamonds,
                            'irons': irons,
                            'gold': gold,
                            'emeralds': emeralds,
                            'blocksplaced': blocksplaced
                        })
                    
                    db_manager.db['users'].update_one(
                        {'discordid': str(player_id)},
                        {'$set': update_data}
                    )
                    result = 'win' if player_id in winning_team else 'lose'
                    ismvp = player_id in mvp_ids
                    await elocal(bot, player_id, result, ismvp, gameid, player_stats)

        
        os.makedirs('temp', exist_ok=True)
        output_path = ScoreImage.generate_score_image(gameid, winningteamnumber, mvp_ids)
        scoring_channel = bot.get_channel(int(config['channels']['scoring']))
        if scoring_channel:
            with open(output_path, 'rb') as image_file:
                await scoring_channel.send(content=all_mentions, file=discord.File(image_file))
        text_channel = bot.get_channel(int(text_channel_id))
        if text_channel:
            with open(output_path, 'rb') as image_file:
                await text_channel.send(file=discord.File(image_file))

        
        warning_embed = embed_builder.build_warning(
            title="Channel Deletion Warning",
            description="This channel will be deleted in 30 seconds."
        )
        if text_channel:
            await text_channel.send(embed=warning_embed)
        await asyncio.sleep(30)
        try:
            try:
                await create_transcript(bot, int(text_channel_id), f"Game #{gameid} Transcript")
            except Exception as transcript_error:
                print(f'Error creating transcript for game {gameid}: {str(transcript_error)}')
            await delete_channel(int(text_channel_id), bot.get_guild(guild_id))
        except Exception as e:
            print(f'Error during channel cleanup: {e}')
    except PermissionError as e:
        print(f"Permission error while creating or accessing the file: {e}")
    except Exception as e:
        print(f'Error scoring game: {e}')
    finally:
        db_manager.close()
