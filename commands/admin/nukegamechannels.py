import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
import yaml
import asyncio
import os

class AdminNukeGameChannelsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.load_config()

    def load_config(self):
        try:
            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                self.games_text_category_id = int(config['categories']['gamestextcategory'])
                self.games_voice_category_id = int(config['categories']['gamesvoicecategory'])
        except Exception as e:
            print(f"Error loading config: {e}")
            self.games_text_category_id = None
            self.games_voice_category_id = None

    @commands.command(name='nukegamechannels', help='Delete game channels from specified categories.\nUsage: !nukegamechannels <delete_only_inactive: true/false> confirm')
    async def nukegamechannels(self, ctx: commands.Context, delete_only_inactive: bool = True, confirm: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('nukegamechannels', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if confirm != "confirm":
                embed = self.bot.embed_builder.build_warning(
                    title='Confirmation Required',
                    description='This command will delete game channels and clean the database.\n'
                                'To proceed, run: `=nukegamechannels true confirm` or `=nukegamechannels false confirm`.'
                )
                await ctx.reply(embed=embed)
                return

            

            text_category = self.bot.get_channel(self.games_text_category_id)
            voice_category = self.bot.get_channel(self.games_voice_category_id)

            if not text_category or not voice_category:
                embed = self.bot.embed_builder.build_error(
                    title="Error",
                    description="Could not find text or voice categories."
                )
                await ctx.reply(embed=embed)
                return

            if delete_only_inactive:
                inactive_games = self.db_manager.find('games', {'state': {'$in': ['scored', 'voided']}})
                game_ids = [game.get('gameid') for game in inactive_games]
                game_channels = self.db_manager.find('gameschannels', {'gameid': {'$in': game_ids}})
            else:
                game_channels = self.db_manager.find('gameschannels', {})

            channel_count = 0
            text_channels_deleted = 0
            voice_channels_deleted = 0

            
            text_channels_to_delete = []
            for channel in text_category.channels:
                if delete_only_inactive:
                    if any(str(channel.id) == gc.get('textchannelid') for gc in game_channels):
                        text_channels_to_delete.append(channel)
                else:
                    text_channels_to_delete.append(channel)

            for channel in text_channels_to_delete:
                try:
                    await channel.delete(reason=f"Game channel cleanup by {ctx.author}")
                    text_channels_deleted += 1
                    channel_count += 1
                except Exception as e:
                    print(f"Error deleting text channel {channel.id}: {e}")

            
            voice_channels_to_delete = []
            for channel in voice_category.channels:
                if delete_only_inactive:
                    if any(str(channel.id) in (gc.get('team1voicechannelid'), gc.get('team2voicechannelid')) for gc in game_channels):
                        voice_channels_to_delete.append(channel)
                else:
                    voice_channels_to_delete.append(channel)

            for channel in voice_channels_to_delete:
                try:
                    await channel.delete(reason=f"Game channel cleanup by {ctx.author}")
                    voice_channels_deleted += 1
                    channel_count += 1
                except Exception as e:
                    print(f"Error deleting voice channel {channel.id}: {e}")

            embed = self.bot.embed_builder.build_success(
                title="Game Channels Cleanup Complete",
                description=(f"Deleted {channel_count} channels in total:\n"
                             f"• {text_channels_deleted} text channels\n"
                             f"• {voice_channels_deleted} voice channels\n\n"
                             f"Note: No database entries were removed.")
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'nukegamechannels command')
            embed = self.bot.embed_builder.build_error(
                description=f'An error occurred: {str(e)}'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(AdminNukeGameChannelsCommands(bot))
