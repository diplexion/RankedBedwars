import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class ThemeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.group(name='theme', invoke_without_command=True)
    async def theme(self, ctx):
        await ctx.reply("Use `=theme list` to view your themes or `=theme change <theme>` to update your theme.")

    @theme.command(name='list')
    async def list_themes(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('theme', 'list', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        try:
            user_settings = self.db_manager.find_one('settings', {'discordid': str(ctx.author.id)})

            if not user_settings:
                embed = self.embed_builder.build_error(
                    title='No Settings Found',
                    description='You don\'t have any settings configured yet.'
                )
            else:
                current_theme = user_settings.get('theme', 'Default')
                owned_themes = user_settings.get('ownedthemes', ['Default'])

                embed = discord.Embed(
                    title='Your Profile Themes',
                    description=f'Current theme: **{current_theme}**\n\n**Owned themes:**\n{", ".join(owned_themes)}',
                    color=discord.Color.blue()
                )
                embed.set_footer(text='Use !theme change <theme> to change your theme')

            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            await self.error_handler.handle_error(e, 'list themes')
            embed = self.embed_builder.build_error(
                description='An error occurred while listing your themes.'
            )
            await ctx.reply(embed=embed, mention_author=False)

    @theme.command(name='change')
    async def change_theme(self, ctx, *, theme_name: str = None):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('theme', 'change', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        if not theme_name:
            await ctx.reply("Please provide a theme name. Example: `=theme change Neon`", mention_author=False)
            return

        try:
            user_settings = self.db_manager.find_one('settings', {'discordid': str(ctx.author.id)})

            if not user_settings or 'ownedthemes' not in user_settings or theme_name not in user_settings['ownedthemes']:
                embed = self.embed_builder.build_error(
                    title='Theme Not Owned',
                    description=f'You don\'t own the theme "{theme_name}". Check your owned themes with `=theme list`.'
                )
                await ctx.reply(embed=embed, mention_author=False)
                return

            success = self.db_manager.update_player_setting(
                str(ctx.author.id),
                'theme',
                theme_name
            )

            if success:
                embed = discord.Embed(
                    title='Theme Updated',
                    description=f'Your profile theme has been set to **{theme_name}**!',
                    color=discord.Color.green()
                )
            else:
                embed = self.embed_builder.build_error(
                    title='Update Failed',
                    description='Failed to update your theme. Please try again later.'
                )

            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            await self.error_handler.handle_error(e, 'change theme')
            embed = self.embed_builder.build_error(
                description='An error occurred while updating your theme.'
            )
            await ctx.reply(embed=embed, mention_author=False)

async def setup(bot):
    await bot.add_cog(ThemeCommands(bot))
