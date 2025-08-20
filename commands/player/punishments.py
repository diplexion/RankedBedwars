import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from datetime import datetime
import bson

class Punishments(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.database_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()

    @commands.command(name='punishments', help='View your ban history or the history of a specific player by IGN or ID.')
    async def punishments(self, ctx, ign: str = None):
        def format_value(value):
            if isinstance(value, bson.timestamp.Timestamp):
                return datetime.fromtimestamp(value.time).strftime('%Y-%m-%d %H:%M:%S')
            return value

        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('punishments', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        user_id = str(ctx.author.id)

        if not ign:
            user_data = self.database_manager.find_one('users', {'discordid': user_id})
            if not user_data:
                await ctx.reply(embed=self.embed_builder.build_error(
                    description="No user data found for your account."
                ))
                return
            ign = user_data.get('ign')

        
        bans = self.database_manager.find('bans', {'ign': ign})
        bans = [{k: format_value(v) for k, v in ban.items()} for ban in bans]
        if not bans:
            await ctx.reply(embed=self.embed_builder.build_warning(
                description=f"No ban history found for IGN: {ign}."
            ))
            return

        
        embeds = []
        for i in range(0, len(bans), 10):
            embed = self.embed_builder.build_info(
                title=f"Ban History for {ign}",
                description=""
            )
            for ban in bans[i:i + 10]:
                is_expired = "Yes" if ban.get('unbanned', False) else "No"
                embed.add_field(
                    name=f"Ban ID: {ban.get('_id', 'Unknown')}",
                    value=(
                        f"**Reason:** {ban.get('reason', 'Unknown')}\n"
                        f"**Duration:** {ban.get('duration', 'Unknown')}\n"
                        f"**Expired:** {is_expired}"
                    ),
                    inline=False
                )
            embeds.append(embed)

        
        current_page = 0

        async def update_message(interaction, page):
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
                await update_message(interaction, current_page)

            for item in view.children:
                item.callback = button_callback

            return view

        await ctx.reply(embed=embeds[current_page], view=create_view(current_page, ctx.author))

async def setup(bot):
    await bot.add_cog(Punishments(bot))
