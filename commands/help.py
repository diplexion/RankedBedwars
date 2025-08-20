import discord
from discord.ext import commands
from discord import app_commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
import os

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.permission_manager = PermissionManager()

    async def build_help_embed_and_view(self):
        
        category_folders = ["dev", "admin", "player", "game", "party"]
        categories = {}

        
        slash_commands_path = os.path.dirname(__file__)

        
        for folder in category_folders:
            folder_path = os.path.join(slash_commands_path, folder)
            if os.path.isdir(folder_path):
                command_list = []
                for file in os.listdir(folder_path):
                    if file.endswith(".py"):
                        command_name = file[:-3]
                        required_roles = self.permission_manager.get_required_roles(command_name)
                        role_names = (
                            "Everyone" if "everyone" in required_roles else ", ".join([f"<@&{role_id}>" for role_id in required_roles])
                        )
                        command_list.append(f"{command_name} (Roles: {role_names})")
                categories[folder.capitalize()] = command_list

        embed = self.embed_builder.build_info(
            title="Help Menu",
            description="Select a category to view its commands."
        )

        
        class CategoryView(discord.ui.View):
            def __init__(self, parent):
                super().__init__(timeout=60)
                self.parent = parent
                self.categories = categories

                self.add_item(discord.ui.Button(label="Dev", style=discord.ButtonStyle.danger, custom_id="Dev"))
                self.add_item(discord.ui.Button(label="Admin", style=discord.ButtonStyle.danger, custom_id="Admin"))
                self.add_item(discord.ui.Button(label="Player", style=discord.ButtonStyle.primary, custom_id="Player"))
                self.add_item(discord.ui.Button(label="Game", style=discord.ButtonStyle.success, custom_id="Game"))
                self.add_item(discord.ui.Button(label="Party", style=discord.ButtonStyle.secondary, custom_id="Party"))

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                selected_category = interaction.data.get("custom_id")
                if selected_category in self.categories:
                    commands_list = "\n".join(self.categories[selected_category])
                    updated_embed = self.parent.embed_builder.build_info(
                        title=f"{selected_category} Commands",
                        description=f"**Commands:**\n{commands_list}"
                    )
                    await interaction.response.edit_message(embed=updated_embed, view=self)
                return True

        return embed, CategoryView(self)

    
    @app_commands.command(name="help", description="View available commands and categories")
    async def help(self, interaction: discord.Interaction):
        embed, view = await self.build_help_embed_and_view()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    
    @commands.command(name="help")
    async def help_prefix(self, ctx: commands.Context):
        embed, view = await self.build_help_embed_and_view()
        await ctx.reply(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))
