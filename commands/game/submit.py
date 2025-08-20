import discord
from discord.ext import commands
from utils.embed_builder import EmbedBuilder
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager

class SubmitGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.database_manager = DatabaseManager()
        self.permission_manager = PermissionManager()

    @commands.command(name='submit')
    async def submit(self, ctx: commands.Context):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('submit', user_roles):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='Permission Denied',
                        description='You do not have permission to use this command.'
                    )
                )
                return

            if not ctx.message.attachments:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title='No Attachment Found',
                        description='You must attach an image to submit a game.'
                    )
                )
                return

            attachment = ctx.message.attachments[0]
            if not attachment.content_type or not attachment.content_type.startswith("image/"):
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title="Invalid Attachment",
                        description="Please upload a valid image file (PNG, JPG, etc.)."
                    )
                )
                return

            
            channel_id = str(ctx.channel.id)
            game_channel = self.database_manager.find_one('gameschannels', {'textchannelid': channel_id})
            if not game_channel:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title="Invalid Channel",
                        description="This command can only be used in a valid games text channel."
                    )
                )
                return

            game_id = game_channel.get('gameid')
            game = self.database_manager.find_one('games', {'gameid': game_id})
            if not game:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title="Game Not Found",
                        description="Game not found."
                    )
                )
                return

            if game.get('state') == 'scored':
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title="Game Already Scored",
                        description="This game has already been scored and cannot be submitted."
                    )
                )
                return

            if game.get('state') == 'submitted':
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        title="Game Already Submitted",
                        description="This game has already been submitted and cannot be submitted again."
                    )
                )
                return

            team1_ids = game.get('team1', [])
            team2_ids = game.get('team2', [])

            team1_igns = []
            for player_id in team1_ids:
                user = self.database_manager.find_one('users', {'discordid': player_id})
                team1_igns.append(user.get('ign', 'Unknown') if user else 'Unknown')

            team2_igns = []
            for player_id in team2_ids:
                user = self.database_manager.find_one('users', {'discordid': player_id})
                team2_igns.append(user.get('ign', 'Unknown') if user else 'Unknown')

            embed = self.embed_builder.build_info(
                title=f"Game #{game_id} Submission",
                description=(
                    f"**Submitted by:** {ctx.author.mention}\n"
                    f"**Team 1 Players:** {', '.join(team1_igns)}\n"
                    f"**Team 2 Players:** {', '.join(team2_igns)}"
                )
            )
            embed.set_image(url=attachment.url)

            scorer_role_id = getattr(self.bot.config['roles'], 'scorer', None) \
                if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'roles') else None
            scorer_ping = f"<@&1388597349277892658>"

            await ctx.reply(content=scorer_ping, embed=embed)

            
            self.database_manager.update_one(
                'games', {'gameid': game_id},
                {'$set': {'state': 'submitted', 'result': 'submitted'}}
            )
            self.database_manager.update_one(
                'recentgames', {'gameid': game_id},
                {'$set': {'state': 'submitted', 'result': 'submitted'}}
            )

            await ctx.reply(
                embed=self.embed_builder.build_success(
                    title="Submission Successful",
                    description="Game submission was successful."
                )
            )

        except Exception as e:
            print(f"Error in submit command: {e}")
            await ctx.reply(
                embed=self.embed_builder.build_error(
                    title="Error",
                    description="An error occurred while submitting the game."
                )
            )

async def setup(bot):
    await bot.add_cog(SubmitGame(bot))
