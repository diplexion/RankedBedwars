import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from managers.permission_manager import PermissionManager
import bson.timestamp
from datetime import datetime

class Strikes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()

    def format_value(self, value):
        if isinstance(value, bson.timestamp.Timestamp):
            return datetime.fromtimestamp(value.time).strftime('%Y-%m-%d %H:%M:%S')
        return value

    @commands.command(name='strikes', help='View strike history of a player')
    async def strikes(self, ctx, ign: str = None):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('strikes', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        user_id = str(ctx.author.id)

        if not ign:
            user_data = self.database_manager.find_one('users', {'discordid': user_id})
            if not user_data:
                await ctx.reply(
                    embed=self.embed_builder.build_error(
                        description="No user data found for your account."
                    ),
                    mention_author=False
                )
                return
            ign = user_data.get('ign')

        strikes = self.database_manager.find('strikes', {'ign': ign})
        strikes = [{k: self.format_value(v) for k, v in strike.items()} for strike in strikes]

        if not strikes:
            await ctx.reply(
                embed=self.embed_builder.build_warning(
                    description=f"No strike history found for IGN: {ign}."
                ),
                mention_author=False
            )
            return

        embeds = []
        for i in range(0, len(strikes), 10):
            embed = self.embed_builder.build_info(
                title=f"Strike History for {ign}",
                description=""
            )
            for strike in strikes[i:i + 10]:
                embed.add_field(
                    name=f"Strike ID: {strike.get('_id', 'Unknown')}",
                    value=(f"**Reason:** {strike.get('reason', 'Unknown')}\n"
                           f"**Date:** {strike.get('date', 'Unknown')}\n"
                           f"**Staff:** {strike.get('staffid', 'Unknown')}"),
                    inline=False
                )
            embeds.append(embed)

        current_page = 0

        async def update_embed(interaction, page):
            await interaction.response.edit_message(embed=embeds[page], view=create_view(page, ctx.author))

        def create_view(page, author):
            view = discord.ui.View()
            if page > 0:
                view.add_item(discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev"))
            if page < len(embeds) - 1:
                view.add_item(discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next"))

            async def button_callback(interaction: discord.Interaction):
                nonlocal current_page
                if interaction.user != author:
                    await interaction.response.send_message("You can't control this pagination.", ephemeral=True)
                    return
                if interaction.data['custom_id'] == 'prev':
                    current_page -= 1
                elif interaction.data['custom_id'] == 'next':
                    current_page += 1
                await update_embed(interaction, current_page)

            for item in view.children:
                item.callback = button_callback

            return view

        await ctx.reply(embed=embeds[current_page], view=create_view(current_page, ctx.author), mention_author=False)

async def setup(bot):
    await bot.add_cog(Strikes(bot))
