from PIL import Image, ImageDraw, ImageFont
import os
import requests
import yaml
from managers.database_manager import DatabaseManager
import discord

db_manager = DatabaseManager()


font_paths = {
    "PoppinsLight": "asserts/fonts/Poppins-ExtraLight.ttf",
    "PoppinsSemiBold": "asserts/fonts/Poppins-SemiBold.ttf",
    "PoppinsMedium": "asserts/fonts/Poppins-Medium.ttf",
    "ADAMCGPRO": "asserts/fonts/ADAM.CG PRO.otf",
    "PoppinsRegular": "asserts/fonts/Poppins-Regular.ttf"
}


image_paths = {
    "bg": "asserts/games/scored.png",
    "mvp": "asserts/games/mvp.png",
    "arrow": "asserts/games/arrow.png"
}


images = {name: Image.open(path).convert("RGBA") for name, path in image_paths.items()}

class ScoreImage:
    @staticmethod
    def generate_score_image(gameid, winningteamnumber, mvp_ids, guild=None):
        
        game_data = db_manager.find_one("games", {"gameid": gameid})
        if not game_data:
            raise ValueError(f"Game with ID {gameid} not found in the database.")

        
        team1 = game_data.get("team1", [])
        team2 = game_data.get("team2", [])
        winning_team = team1 if winningteamnumber == 1 else team2
        losing_team = team2 if winningteamnumber == 1 else team1

        
        players = []
        for player_id in winning_team + losing_team:
            player_data = db_manager.find_one("users", {"discordid": player_id})
            recent_game = db_manager.find_one("recentgames", {"discordid": player_id, "gameid": gameid})
            if player_data and recent_game:
                players.append({
                    "username": player_data.get("ign", "Unknown"),
                    "team": "winning" if player_id in winning_team else "losing",
                    "oldElo": player_data.get("elo", 0) - recent_game.get("elochange", 0),
                    "newElo": player_data.get("elo", 0),
                    "mvp": player_id in mvp_ids  
                })

        
        winners = [p for p in players if p['team'] == "winning"]
        losers = [p for p in players if p['team'] == "losing"]
        bg = images['bg']
        canvas = bg.copy()
        draw = ImageDraw.Draw(canvas)

        
        draw.text((120, 45), f"GAME #{gameid}", fill="#757474",
                  font=ImageFont.truetype(font_paths["PoppinsLight"], size=54))

        
        with open("configs/config.yml", "r") as config_file:
            config = yaml.safe_load(config_file)
            servername = config['server']['servername']
            invitelink = config['server']['invitelink']

        draw.text((120, 952), f"{servername}", fill="#757474",
                  font=ImageFont.truetype(font_paths["PoppinsLight"], size=54))

        
        invitelink_bbox = draw.textbbox((0, 0), invitelink, font=ImageFont.truetype(font_paths["PoppinsLight"], size=54))
        invitelink_width = invitelink_bbox[2] - invitelink_bbox[0]

        
        adjusted_x = 1612 - invitelink_width / 2 if 1612 + invitelink_width / 2 <= canvas.width else canvas.width - invitelink_width - 1

        draw.text((adjusted_x, 952), f"{invitelink}", fill="#757474",
                  font=ImageFont.truetype(font_paths["PoppinsLight"], size=54))

        ScoreImage.draw_card(draw, 185, 170, winners, canvas, guild)
        ScoreImage.draw_card(draw, 185, 600, losers, canvas, guild)

        output_path = f"temp/game_{gameid}_results.png"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        return output_path

    @staticmethod
    def draw_card(draw, pos_x, pos_y, team, canvas, guild=None):
        
        line_height = 93  
        for index, player in enumerate(team):
            ScoreImage.draw_line_section1(draw, pos_x, pos_y + (index * line_height), player, canvas, guild)

    @staticmethod
    def get_rank_icon_from_role(guild, rank_name):
        if not guild:
            return None
            
        try:
            role = discord.utils.get(guild.roles, name=rank_name)
            if not role:
                print(f"Role not found: {rank_name}")
                return None
                
            if role.display_icon:
                from io import BytesIO
                response = requests.get(role.display_icon.url)
                if response.status_code == 200:
                    return Image.open(BytesIO(response.content)).convert("RGBA").resize((40, 40))
                    
            if role.unicode_emoji:
                return Image.open(f"asserts/ranks/{rank_name.lower()}.png").convert("RGBA").resize((40, 40))
                
            emoji = discord.utils.get(guild.emojis, name=f"{rank_name.lower()}_rank")
            if emoji:
                response = requests.get(emoji.url)
                if response.status_code == 200:
                    return Image.open(BytesIO(response.content)).convert("RGBA").resize((40, 40))
                    
            print(f"No icon found for rank: {rank_name}")
            return None
            
        except Exception as e:
            print(f"Error getting rank icon for {rank_name}: {str(e)}")
            return None

    @staticmethod
    def draw_rank_transition(canvas, draw, old_rank, new_rank, rank_x, icon_y, icon_spacing=60, guild=None):
        old_icon_x = int(rank_x - icon_spacing)
        new_icon_x = int(rank_x + icon_spacing)
        icon_center_y = int(icon_y + 40 // 2)
        old_icon_img = ScoreImage.get_rank_icon_from_role(guild, old_rank) if guild else None
        new_icon_img = ScoreImage.get_rank_icon_from_role(guild, new_rank) if guild else None
        arrow_img = images.get('arrow').resize((40, 30))
        if old_icon_img and new_icon_img and arrow_img:
            canvas.paste(old_icon_img, (old_icon_x, icon_y), old_icon_img)
            arrow_x = int((old_icon_x + 40 + new_icon_x) / 2 - 20)
            arrow_y = int(icon_center_y - 20)
            canvas.paste(arrow_img, (arrow_x, arrow_y), arrow_img)
            canvas.paste(new_icon_img, (new_icon_x, icon_y), new_icon_img)

    @staticmethod
    def draw_line_section1(draw, pos_x, pos_y, player, canvas, guild=None):
        
        try:
            avatar_url = f"https://mineskin.eu/avatar/{player['username']}/40"
            avatar_image = Image.open(requests.get(avatar_url, stream=True).raw).convert("RGBA")
        except Exception:
            avatar_image = Image.open("asserts/fallbacks/steve.png").convert("RGBA")

        canvas.paste(avatar_image, (int(pos_x), int(pos_y)), avatar_image)

        
        username_font = ImageFont.truetype(font_paths["ADAMCGPRO"], size=40)
        draw.text((pos_x + 58.5, pos_y + 3), player['username'], fill="white", font=username_font)

        
        username_bbox = draw.textbbox((0, 0), player['username'], font=username_font)
        username_width = username_bbox[2] - username_bbox[0]

        
        if player['mvp']:
            mvp_img = images['mvp']
            
            mvp_x = int(pos_x + 58.5 + username_width + 10)
            mvp_y = int(pos_y - 5)  
            
            
            
            
            canvas.paste(mvp_img, (mvp_x, mvp_y), mvp_img)

        
        elo_change_text = f"{player['newElo'] - player['oldElo']:+}"
        old_elo_text = str(player['oldElo'])
        new_elo_text = str(player['newElo'])

        
        elo_change_bbox = draw.textbbox((0, 0), elo_change_text, font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))
        old_elo_bbox = draw.textbbox((0, 0), old_elo_text, font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))
        new_elo_bbox = draw.textbbox((0, 0), new_elo_text, font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))

        
        elo_change_width = elo_change_bbox[2] - elo_change_bbox[0]
        old_elo_width = old_elo_bbox[2] - old_elo_bbox[0]
        new_elo_width = new_elo_bbox[2] - new_elo_bbox[0]

        
        draw.text((pos_x + 1130 - elo_change_width / 2, pos_y + 3), elo_change_text, fill="white",
                  font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))
        draw.text((pos_x + 1291 - old_elo_width / 2, pos_y + 3), old_elo_text, fill="#757474",
                  font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))
        draw.text((pos_x + 1499 - new_elo_width / 2, pos_y + 3), new_elo_text, fill="white",
                  font=ImageFont.truetype(font_paths["ADAMCGPRO"], size=40))

        
        old_rank = ScoreImage.get_rank_from_elo(player['oldElo'])
        new_rank = ScoreImage.get_rank_from_elo(player['newElo'])
        
        
        rank_x = pos_x + 850
        icon_spacing = 60  

        
        if guild:
            old_icon = ScoreImage.get_rank_icon_from_role(guild, old_rank)
            new_icon = ScoreImage.get_rank_icon_from_role(guild, new_rank)
            if old_rank == new_rank and new_icon:
                canvas.paste(new_icon, (int(rank_x), int(pos_y)), new_icon)
            elif old_icon and new_icon:
                ScoreImage.draw_rank_transition(canvas, draw, old_rank, new_rank, rank_x, int(pos_y), icon_spacing, guild)
        

    @staticmethod
    def draw_rank(draw, pos_x, pos_y, elo):
        rank = ScoreImage.get_rank_from_elo(elo)
        draw.text((pos_x, pos_y), rank, fill="white",
                  font=ImageFont.truetype(font_paths["PoppinsMedium"], size=40))

    @staticmethod
    def get_rank_from_elo(elo):
        elos = list(db_manager.find('elos', {}, limit=None))
        if not elos:
            
            if elo < 100:
                return "coal"
            elif elo < 300:
                return "iron"
            elif elo < 600:
                return "gold"
            elif elo < 1000:
                return "diamond"
            elif elo < 1500:
                return "emerald"
            elif elo < 2000:
                return "platinum"
            else:
                return "obsidian"
        
        elos.sort(key=lambda x: x.get('minelo', 0))
        for rank in elos:
            minelo = rank.get('minelo', 0)
            maxelo = rank.get('maxelo', 0)
            if minelo <= elo <= maxelo:
                return rank.get('rankname', 'unknown')
        return "unknown"
