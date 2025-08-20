import os
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, List, Tuple, Optional
import yaml
import math
import asyncio
from concurrent.futures import ThreadPoolExecutor

class RichTheme:
    
    @staticmethod
    async def _generate_shadow_async(skin_data: BytesIO) -> Image.Image:
        def _process_shadow():
            shadow_image = Image.open(skin_data).convert("RGBA")
            shadow_image = shadow_image.resize((250, 420))
            shadow_data = shadow_image.getdata()
            new_shadow_data = []
            for item in shadow_data:
                if item[3] > 0:  
                    new_shadow_data.append((0, 0, 0, int(item[3] * 0.4)))
                else:
                    new_shadow_data.append(item)  
            shadow_image.putdata(new_shadow_data)
            return shadow_image

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            return await loop.run_in_executor(pool, _process_shadow)
    
    @staticmethod
    async def generate_image(player_data: Dict[str, Any], recent_games: List[Dict[str, Any]], calculate_rating, calculate_position) -> BytesIO:
        themes_folder = os.path.join("asserts", "themes")
        fonts_folder = os.path.join("asserts", "fonts")
        theme_image_path = os.path.join(themes_folder, "rich.png")

        config_path = os.path.join("configs", "config.yml")
        server_name = "ZeroCode" 
        invite_link = "discord.gg/zerocode" 
        
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                server_name = config.get('server', {}).get('servername', server_name)
                invite_link = config.get('server', {}).get('invitelink', invite_link)
        except Exception as e:
            print(f"Error loading config.yml: {e}")
        image = Image.open(theme_image_path).convert("RGBA")
        draw = ImageDraw.Draw(image)
        
        font_files = [
            os.path.join(fonts_folder, "font3.ttf"),
            os.path.join(fonts_folder, "ADAM.CG PRO.otf"),
            os.path.join(fonts_folder, "Poppins-Medium.ttf"),
            os.path.join(fonts_folder, "Poppins-Regular.ttf"),
        ]
        
        font_path = None
        for font_file in font_files:
            if os.path.exists(font_file):
                font_path = font_file
                break
        
        skin_data = RichTheme._fetch_skin(player_data['ign'])
        shadow_task = None
        if skin_data:
            shadow_task = asyncio.create_task(RichTheme._generate_shadow_async(skin_data))
            
            skin_image = Image.open(skin_data).convert("RGBA")
            skin_image = skin_image.resize((250, 420))
            
            if shadow_task:
                shadow_image = await shadow_task
                image.paste(shadow_image, (105 + 15, 110 + 15), shadow_image)
            
            image.paste(skin_image, (105, 110), skin_image) 
        
        def draw_centered_text(text, x, y, font_size, fill_color="#FFFFFF"):
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            
            left, top, right, bottom = font.getbbox(text)
            text_width = right - left
            text_height = bottom - top
            
            position = (x - text_width // 2, y - text_height // 2)
            
            draw.text(position, text, fill=fill_color, font=font)
        
        def draw_left_text(text, x, y, font_size, fill_color="#FFFFFF"):
            font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
            draw.text((x, y), text, fill=fill_color, font=font)
        
        draw_centered_text(server_name, 640, 40, 40)
        
        draw_centered_text(invite_link, 640, 660, 20)
        
        if len(player_data['ign']) <= 10:
            ign_font_size = 34
        else:
            ign_font_size = 20
        draw_centered_text(player_data['ign'], 258, 574, ign_font_size)

        u = 28

        main_stats = {
            "WINS": [str(player_data['wins']), 517, 180 + u, 85],
            "POS.": ["#" + str(calculate_position(player_data['discordid'])), 780, 180 + u, 85],
            "MVPS": [str(player_data['mvps']), 1047, 180 + u, 85],
            "RATING": [str(player_data['elo']), 517, 490 + u, 85]
        }
        
        for label, values in main_stats.items():
            draw_centered_text(values[0], values[1], values[2], values[3])
        
        normal_stats = {
            "W/L": [RichTheme._calculate_wl_ratio(player_data), 517, 315 + 7, 30],
            "RATE": [f"{RichTheme._calculate_mvp_rate(player_data):.0f}%", 1047, 315 + 7, 30]
        }
        
        for label, values in normal_stats.items():
            text = values[0] + " " + label
            draw_centered_text(text, values[1], values[2], values[3])
        
        arrow_x = 710  
        arrow_y = 315 + 10

        current_elo = player_data.get('elo', 0)
        from managers.database_manager import DatabaseManager
        db_manager = DatabaseManager()
        
        all_ranks = list(db_manager.db['elos'].find().sort([('minelo', 1)]))
        
        next_rank = None
        for rank in all_ranks:
            if rank['minelo'] > current_elo:
                next_rank = rank
                break
        
        if next_rank:
            elo_needed = next_rank['minelo'] - current_elo
            win_elo = 0
            current_rank = db_manager.find_one('elos', {'minelo': {'$lte': current_elo}, 'maxelo': {'$gte': current_elo}})
            if current_rank:
                win_elo = current_rank.get('winelo', 25)  
            
            wins_needed = math.ceil(elo_needed / win_elo) if win_elo > 0 else 0
            next_rank_text = f"IN {wins_needed} WINS"
        else:
            next_rank_text = "MAX RANK"
        
        draw_centered_text(next_rank_text, 795, 315 + 7, 30)
        
        arrow_points = [
            (arrow_x - 18, arrow_y + 2),    
            (arrow_x - 8, arrow_y - 12),    
            (arrow_x + 2, arrow_y + 2)      
        ]
        draw.polygon(arrow_points, fill="#FFFFFF")
        
        recent_games = recent_games[:10] if len(recent_games) >= 10 else recent_games + [None] * (10 - len(recent_games))
        recent_games_y = 475
        left_center_x = 700
        for i, game in enumerate(recent_games[:5]):
            if game:
                game_id = f"Game #{game.get('gameid', 'N/A')}"
                game_result = game.get('result', 'unknown')
                if game_result == 'win':
                    color = "#4CAF50"  
                elif game_result == 'lose':
                    color = "#F44336"  
                elif game_result == 'voided':
                    color = "#FFC107"  
                elif game_result == 'pending':
                    color = "#FFC107" 
                elif game_result == 'submitted':
                    color = "#FF9800" 
                else:
                    color = "#777777"
            else:
                game_id = "No Game"
                color = "#777777"

            draw_left_text(game_id, left_center_x, recent_games_y + (i * 28), 24, color)

        right_center_x = 945
        for i, game in enumerate(recent_games[5:10]):
            if game:
                game_id = f"Game #{game.get('gameid', 'N/A')}"
                game_result = game.get('result', 'unknown')
                if game_result == 'win':
                    color = "#4CAF50" 
                elif game_result == 'loss':
                    color = "#F44336" 
                elif game_result == 'voided':
                    color = "#FFC107"  
                elif game_result == 'pending':
                    color = "#FFC107" 
                elif game_result == 'submitted':
                    color = "#FF9800" 
                else:
                    color = "#777777"
            else:
                game_id = "No Game"
                color = "#777777"

            draw_left_text(game_id, right_center_x, recent_games_y + (i * 28), 24, color)
        
        output = BytesIO()
        image.save(output, format='PNG')
        output.seek(0)
        
        return output
    
    @staticmethod
    def _fetch_skin(ign: str, pose: str = 'fullbody') -> Optional[BytesIO]:
        skin_api_url = "https://nmsr.nickac.dev"
        try:
            url = f"{skin_api_url}/{pose}/{ign}"
            response = requests.get(url)
            if response.status_code == 200:
                return BytesIO(response.content)
        except Exception as e:
            print(f"Error fetching skin: {e}")
        return None
    
    @staticmethod
    def _calculate_wl_ratio(player_data: Dict[str, Any]) -> str:
        wins = player_data.get('wins', 0)
        losses = player_data.get('losses', 0)
        wl_ratio = wins / max(losses, 1)  
        return f"{wl_ratio:.1f}"
    
    @staticmethod
    def _calculate_mvp_rate(player_data: Dict[str, Any]) -> float:
        mvps = player_data.get('mvps', 0)
        games_played = player_data.get('gamesplayed', 0)
        if games_played > 0:
            return (mvps / games_played) * 100
        return 0
