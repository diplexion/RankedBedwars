import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
import asyncio

class StrikeRequestCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)
        self.active_votes = {}

    @commands.command(name='strikerequest', help='Request a strike for a player from a specific game', aliases=['sr'])

    async def strikerequest(self, ctx, target_mention: discord.Member, game_id: str, *, reason: str):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('strikerequest', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            
            game = self.db_manager.find_one('games', {'gameid': game_id.upper()})
            if not game:
                embed = self.embed_builder.build_error(description=f'No game found with ID: {game_id}')
                await ctx.reply(embed=embed)
                return

            target_player = self.db_manager.find_one('users', {'discordid': str(target_mention.id)})
            if not target_player:
                embed = self.embed_builder.build_error(description=f'Target player <@{target_mention.id}> not found in database')
                await ctx.reply(embed=embed)
                return

            sender_data = self.db_manager.find_one('users', {'discordid': str(ctx.author.id)})
            if not sender_data:
                embed = self.embed_builder.build_error(description='You need to be registered to use this command')
                await ctx.reply(embed=embed)
                return

            
            team1 = game.get('team1', [])
            team2 = game.get('team2', [])
            all_players = team1 + team2
            target_id = str(target_player['discordid'])
            sender_id = str(ctx.author.id)

            
            if target_id in team1:
                target_team = team1
            elif target_id in team2:
                target_team = team2
            else:
                embed = self.embed_builder.build_error(description=f'Target player <@{target_mention.id}> was not in game {game_id}')
                await ctx.reply(embed=embed)
                return

            if sender_id not in target_team:
                embed = self.embed_builder.build_error(description='You can only request a strike for a player on your own team, and you must be on that team.')
                await ctx.reply(embed=embed)
                return

            
            team_players = target_team

            strike_request_channel = self.bot.get_channel(int(self.bot.config['channels']['strikerequest']))
            if not strike_request_channel:
                embed = self.embed_builder.build_error(description='Strike request channel not found')
                await ctx.reply(embed=embed)
                return

            class VoteButtons(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=600)
                    self.votes = {'yes': set(), 'no': set()}
                    self.done = asyncio.Event()
                    self.message = None

                async def on_timeout(self):
                    self.done.set()
                    for child in self.children:
                        child.disabled = True
                    if self.message:
                        await self.message.edit(view=self)

                @discord.ui.button(label='Yes', style=discord.ButtonStyle.green)
                async def yes_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    voter_id = str(button_interaction.user.id)
                    if voter_id not in team_players:
                        await button_interaction.response.send_message('Only players from the same team can vote!', ephemeral=True)
                        return
                    if voter_id == target_id:
                        await button_interaction.response.send_message('You cannot vote on your own strike request!', ephemeral=True)
                        return
                    self.votes['yes'].add(button_interaction.user.id)
                    self.votes['no'].discard(button_interaction.user.id)
                    await button_interaction.response.send_message('Vote recorded!', ephemeral=True)

                @discord.ui.button(label='No', style=discord.ButtonStyle.red)
                async def no_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    voter_id = str(button_interaction.user.id)
                    if voter_id not in team_players:
                        await button_interaction.response.send_message('Only players from the same team can vote!', ephemeral=True)
                        return
                    if voter_id == target_id:
                        await button_interaction.response.send_message('You cannot vote on your own strike request!', ephemeral=True)
                        return
                    self.votes['no'].add(button_interaction.user.id)
                    self.votes['yes'].discard(button_interaction.user.id)
                    await button_interaction.response.send_message('Vote recorded!', ephemeral=True)

            view = VoteButtons()

            embed = self.embed_builder.build_info(
                title='Strike Request Vote',
                description=f'**Target Player:** <@{target_mention.id}>\n'
                            f'**Game ID:** {game_id}\n'
                            f'**Reason:** {reason}\n'
                            f'**Requested by:** <@{ctx.author.id}>\n\n'
                            f'Only players from the same team as the target can vote using the buttons below.\n'
                            f'Voting will end in 10 minutes.'
            )

            vote_message = await strike_request_channel.send(embed=embed, view=view)
            view.message = vote_message

            thread = await vote_message.create_thread(
                name=f'Strike Vote Discussion - {game_id} - Team',
                auto_archive_duration=60
            )

            mention_message = ' '.join(
                f'<@{pid}>' for pid in team_players if pid != target_id
            )
            await thread.send(f'Vote Discussion Started\n{mention_message}')


            vote_id = f"{game_id}_{target_player['discordid']}"
            self.active_votes[vote_id] = {
                'message': vote_message,
                'view': view,
                'thread': thread,
                'target_player': target_player,
                'game_id': game_id,
                'reason': reason
            }

            await view.done.wait()

            yes_votes = len(view.votes['yes'])
            no_votes = len(view.votes['no'])
            total_possible_voters = len(team_players) - 1

            if yes_votes > no_votes and yes_votes > total_possible_voters / 2:
                success = await self.bot.strikes_manager.apply_strike(
                    discord_id=str(target_player['discordid']),
                    staff_id=str(self.bot.user.id),
                    ign=target_player['ign'],
                    reason=f'Community vote from game {game_id}. Reason: {reason}'
                )
                result_embed = self.embed_builder.build_success(
                    title='Strike Vote Results',
                    description=f'Vote Passed: Strike applied to <@{target_mention.id}>\n'
                                f'Reason: {reason}\n'
                                f'Yes Votes: {yes_votes}\n'
                                f'No Votes: {no_votes}'
                )
            else:
                result_embed = self.embed_builder.build_error(
                    title='Strike Vote Results',
                    description=f'Vote Failed: No strike applied to <@{target_mention.id}>\n'
                                f'Reason: {reason}\n'
                                f'Yes Votes: {yes_votes}\n'
                                f'No Votes: {no_votes}'
                )

            await vote_message.reply(embed=result_embed)
            await thread.send(embed=result_embed)
            await ctx.reply(embed=result_embed)

            del self.active_votes[vote_id]

        except Exception as e:
            await self.error_handler.handle_error(e, 'strike request command')
            embed = self.embed_builder.build_error(
                description='An error occurred while processing the strike request.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(StrikeRequestCommand(bot))
