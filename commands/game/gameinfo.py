import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class GameInfoCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='gameinfo', help='Get info about a game. Usage: !gameinfo [game_id]')
    async def gameinfo(self, ctx, game_id: str = None):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('gameinfo', user_roles):
                embed = self.bot.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if not game_id:
                current_channel_id = str(ctx.channel.id)
                game_channel = self.db_manager.find_one('gameschannels', {'textchannelid': current_channel_id})
                if not game_channel:
                    embed = self.bot.embed_builder.build_error(
                        description='Please provide a game ID or use this command in a game channel.'
                    )
                    await ctx.reply(embed=embed)
                    return
                game_id = game_channel.get('gameid')
            else:
                game_id = game_id.upper()

            game = self.db_manager.find_one('games', {'gameid': game_id})
            if not game:
                embed = self.bot.embed_builder.build_error(
                    description=f'No game found with ID: {game_id}.'
                )
                await ctx.reply(embed=embed)
                return

            game_channel = self.db_manager.find_one('gameschannels', {'gameid': game_id})

            
            mvp_ids = game.get('mvps', [])
            mvp_display = "N/A"
            if isinstance(mvp_ids, list) and mvp_ids:
                mvp_display = ""
                for mvp_id in mvp_ids:
                    mvp_info = self.db_manager.find_one('users', {'discordid': str(mvp_id)})
                    if mvp_info and 'ign' in mvp_info:
                        mvp_display += f"<@{mvp_id}> `{mvp_info['ign']}`\n"
                    else:
                        mvp_display += f"<@{mvp_id}> `Player unregistered`\n"
                mvp_display = mvp_display.strip()

            
            game_date = game.get('date')
            formatted_date = 'N/A'
            if game_date:
                try:
                    dt = getattr(game_date, 'as_datetime', lambda: game_date)()
                    formatted_date = dt.strftime('%d %b %Y')
                except Exception:
                    formatted_date = str(game_date)

            
            game_info = (
                f"**Game ID:** {game.get('gameid', 'N/A')} "
                f"**Date:** {formatted_date}\n"
                f"**State:** {game.get('state', 'N/A')}\n"
                f"**MVP:** {mvp_display}\n"
                f"**Winners**\n"
            )

            
            winning_list = ""
            for player_id in game.get('winningteam', []):
                info = self.db_manager.find_one('users', {'discordid': str(player_id)})
                winning_list += f"      - <@{player_id}> `{info['ign'] if info and 'ign' in info else 'Player unregistered'}`\n"
            if not winning_list:
                winning_list = "      None\n"

            
            losing_list = ""
            for player_id in game.get('loosingteam', []):
                info = self.db_manager.find_one('users', {'discordid': str(player_id)})
                losing_list += f"      - <@{player_id}> `{info['ign'] if info and 'ign' in info else 'Player unregistered'}`\n"
            if not losing_list:
                losing_list = "      None\n"

            
            team1_list = ""
            for player_id in game.get('team1', []):
                info = self.db_manager.find_one('users', {'discordid': str(player_id)})
                team1_list += f"      - <@{player_id}> `{info['ign'] if info and 'ign' in info else 'Player unregistered'}`\n"
            if not team1_list:
                team1_list = "      None\n"

            
            team2_list = ""
            for player_id in game.get('team2', []):
                info = self.db_manager.find_one('users', {'discordid': str(player_id)})
                team2_list += f"      - <@{player_id}> `{info['ign'] if info and 'ign' in info else 'Player unregistered'}`\n"
            if not team2_list:
                team2_list = "      None\n"

            if game_channel:
                picking_voice = game_channel.get('pickingvoicechannelid')
                picking_display = f"<#{picking_voice}>" if picking_voice and picking_voice != 'Maybe its not a Picking season.' else "Maybe its not a Picking season."

                game_info += (
                    f"\n**Voice Channels:**\n"
                    f" - Team 1: <#{game_channel.get('team1voicechannelid', 'N/A')}>\n"
                    f" - Team 2: <#{game_channel.get('team2voicechannelid', 'N/A')}>\n"
                    f" - Picking: {picking_display}\n"
                    f"\n**Text Channel:** <#{game_channel.get('textchannelid', 'N/A')}>\n"
                )

            
            embed = self.bot.embed_builder.build_info(
                title=f'Game Information (ID: {game_id})',
                description=game_info
            )
            embed.add_field(name="Winners", value=winning_list, inline=False)
            embed.add_field(name="Losers", value=losing_list, inline=True)
            embed.add_field(name="Team 1", value=team1_list, inline=False)
            embed.add_field(name="Team 2", value=team2_list, inline=True)

            await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'gameinfo command')
            embed = self.bot.embed_builder.build_error(
                description='An error occurred while fetching game information. Please try again later.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(GameInfoCommand(bot))
