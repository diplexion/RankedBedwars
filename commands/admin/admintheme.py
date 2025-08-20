import discord
from discord.ext import commands
from typing import List
import os
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder

class AdminThemeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.themes_folder = os.path.join('themes')

    def get_available_themes(self) -> List[str]:
        try:
            theme_files = [f for f in os.listdir(self.themes_folder) 
                           if os.path.isfile(os.path.join(self.themes_folder, f)) 
                           and f.endswith('.py')
                           and f != '__init__.py']
            return [os.path.splitext(f)[0] for f in theme_files]
        except Exception as e:
            print(f"Error getting available themes: {e}")
            return []

    @commands.group(name='admintheme')
    async def admintheme(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply("Missing subcommannd! Available: list/give/remove")

    @admintheme.command(name='list', help='List all available themes in the system')
    async def list_themes(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('admin_theme', 'list', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            themes = self.get_available_themes()

            if not themes:
                embed = self.embed_builder.build_warning(
                    title='No Themes Available',
                    description='No themes were found in the themes folder.'
                )
            else:
                theme_list = '\n'.join([f"• {theme}" for theme in themes])
                embed = self.embed_builder.build_info(
                    title='Available Themes',
                    description=f"The following themes are available:\n\n{theme_list}"
                )

                themes_assets_path = os.path.join('asserts', 'themes')
                if os.path.exists(themes_assets_path):
                    image_files = [f for f in os.listdir(themes_assets_path) 
                                   if os.path.isfile(os.path.join(themes_assets_path, f)) 
                                   and f.endswith(('.png', '.jpg', '.jpeg'))]
                    if image_files:
                        image_list = '\n'.join([f"• {os.path.splitext(img)[0]}" for img in image_files])
                        embed.add_field(
                            name="Theme Images", 
                            value=f"The following theme images are available:\n\n{image_list}",
                            inline=False
                        )

            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Error listing themes: {e}")
            embed = self.embed_builder.build_error(
                description='An error occurred while listing themes.'
            )
            await ctx.reply(embed=embed)

    @admintheme.command(name='give', help='Give a theme to a user')
    async def give_theme(self, ctx, member: discord.Member, theme_name: str):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('admin_theme', 'give', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            available_themes = self.get_available_themes()
            if theme_name not in available_themes:
                embed = self.embed_builder.build_error(
                    title='Invalid Theme',
                    description=f'The theme "{theme_name}" does not exist.'
                )
                await ctx.reply(embed=embed)
                return

            user_settings = self.db_manager.find_one('settings', {'discordid': str(member.id)})
            if not user_settings:
                self.db_manager.insert('settings', {
                    'discordid': str(member.id),
                    'isprefixtoggled': False,
                    'ispartyinvitestoggled': False,
                    'isscoringpingtoggled': False,
                    'staticnickname': False,
                    'ownedthemes': [theme_name],
                    'theme': theme_name
                })
                embed = self.embed_builder.build_success(
                    description=f'Successfully gave theme "{theme_name}" to {member.mention} and set it as active.'
                )
            else:
                owned_themes = user_settings.get('ownedthemes', ['Default'])
                if theme_name in owned_themes:
                    embed = self.embed_builder.build_warning(
                        description=f'{member.mention} already owns the "{theme_name}" theme.'
                    )
                else:
                    owned_themes.append(theme_name)
                    self.db_manager.update_one(
                        'settings',
                        {'discordid': str(member.id)},
                        {'$set': {'ownedthemes': owned_themes}},
                        upsert=True
                    )
                    embed = self.embed_builder.build_success(
                        description=f'Successfully gave theme "{theme_name}" to {member.mention}.'
                    )
            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Error giving theme: {e}")
            embed = self.embed_builder.build_error(
                description='An error occurred while giving the theme.'
            )
            await ctx.reply(embed=embed)

    @admintheme.command(name='remove', help='Remove a theme from a user')
    async def remove_theme(self, ctx, member: discord.Member, theme_name: str):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('admin_theme', 'remove', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            user_settings = self.db_manager.find_one('settings', {'discordid': str(member.id)})
            if not user_settings or 'ownedthemes' not in user_settings:
                embed = self.embed_builder.build_error(
                    description=f'{member.mention} does not have any themes to remove.'
                )
                await ctx.reply(embed=embed)
                return

            owned_themes = user_settings.get('ownedthemes', ['Default'])
            if theme_name not in owned_themes:
                embed = self.embed_builder.build_error(
                    description=f'{member.mention} does not own the "{theme_name}" theme.'
                )
                await ctx.reply(embed=embed)
                return

            if theme_name == 'Default':
                embed = self.embed_builder.build_error(
                    description=f'Cannot remove the Default theme from {member.mention}.'
                )
                await ctx.reply(embed=embed)
                return

            if len(owned_themes) == 1:
                embed = self.embed_builder.build_error(
                    description=f'Cannot remove the last theme from {member.mention}.'
                )
                await ctx.reply(embed=embed)
                return

            owned_themes.remove(theme_name)

            if user_settings.get('theme') == theme_name:
                new_theme = 'Default' if 'Default' in owned_themes else owned_themes[0]
                self.db_manager.update_one(
                    'settings',
                    {'discordid': str(member.id)},
                    {'$set': {'ownedthemes': owned_themes, 'theme': new_theme}},
                    upsert=True
                )
                embed = self.embed_builder.build_success(
                    description=f'Removed theme "{theme_name}" from {member.mention}. Theme switched to "{new_theme}".'
                )
            else:
                self.db_manager.update_one(
                    'settings',
                    {'discordid': str(member.id)},
                    {'$set': {'ownedthemes': owned_themes}},
                    upsert=True
                )
                embed = self.embed_builder.build_success(
                    description=f'Removed theme "{theme_name}" from {member.mention}.'
                )

            await ctx.reply(embed=embed)

        except Exception as e:
            print(f"Error removing theme: {e}")
            embed = self.embed_builder.build_error(
                description='An error occurred while removing the theme.'
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(AdminThemeCommands(bot))
