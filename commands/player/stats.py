import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.permission_manager import PermissionManager
import io
import importlib
import os
import sys
import asyncio

class PlayerImageStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.permission_manager = PermissionManager()


    def _calculate_player_position(self, discord_id: str) -> int:
        all_players = list(self.database_manager.db['users'].find({}).sort([('elo', -1)]))
        
        for i, player in enumerate(all_players):
            if player['discordid'] == str(discord_id):
                return i + 1
        
        return 0

    def get_theme_generator(self, theme_name: str):
        try:
            themes_path = os.path.join(os.getcwd(), "themes")
            if themes_path not in sys.path:
                sys.path.append(themes_path)
            
            module = importlib.import_module(f"themes.{theme_name}")
            
            class_name = f"{theme_name.capitalize()}Theme"
            theme_class = getattr(module, class_name)
            
            return theme_class
        except (ImportError, AttributeError) as e:
            print(f"Error importing theme {theme_name}: {e}")
            
            module = importlib.import_module("themes.elite")
            return getattr(module, "EliteTheme")

    @commands.command(name='stats', help='View player statistics as an image', aliases=['statistics', 'i', 'info'])
    async def stats(self, ctx: commands.Context, *, identifier: discord.Member = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('stats', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    ),
                    mention_author=False
                )
                return

            user_id = None
            if identifier:
                user_id = str(identifier.id)
            else:
                user_id = str(ctx.author.id)

            player = self.database_manager.find_one('users', {'discordid': user_id})
            if not player:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Player Not Found',
                        description='No stats found for the specified user.'
                    ),
                    mention_author=False
                )
                return

            try:
                recent_games = list(self.database_manager.db['recentgames'].find({'discordid': user_id}))
                recent_games.sort(key=lambda x: int(x.get('id', '0')), reverse=True)
                recent_games = recent_games[:10]
            except Exception as e:
                print(f"Error sorting recent games numerically: {e}")
                recent_games = list(self.database_manager.db['recentgames'].find(
                    {'discordid': user_id}
                ).sort([('id', -1)]).limit(10))

            settings = self.database_manager.find_one('settings', {'discordid': user_id})
            theme_name = settings.get('theme', 'elite') if settings else 'elite'

            msg = await ctx.reply(f"Generating stats image for **{player['ign']}**...")

            try:
                theme_generator = self.get_theme_generator(theme_name)
                image_bytes = await theme_generator.generate_image(
                    player_data=player,
                    recent_games=recent_games,
                    calculate_rating=self.database_manager.calculate_rating,
                    calculate_position=self._calculate_player_position
                )

                file = discord.File(fp=image_bytes, filename=f"{player['ign']}_stats.png")
                await msg.edit(content=f"**{player['ign']}'s Stats**", attachments=[file])

            except Exception as e:
                await self.error_handler.handle_error(e, 'generating image')
                await msg.edit(content=f"❌ Error generating stats image: {str(e)}")

        except Exception as e:
            await self.error_handler.handle_error(e, 'stats command top-level')
            await ctx.reply(
                f"❌ An error occurred while generating the stats image. Please try again later.",
                mention_author=False
            )

async def setup(bot):
    await bot.add_cog(PlayerImageStats(bot))
