import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler
from managers.database_manager import DatabaseManager

class BoosterCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='booster', help='Set the ELO and XP multiplier for queues.\nUsage: !booster <multiplier>\nExample: !booster 2.5')
    async def booster(self, ctx: commands.Context, multiplier: str = None):
        try:
            valid_values = ['1', '1.5', '2', '2.5', '3']
            value_name_map = {
                '1': '1x (Default)',
                '1.5': '1.5x',
                '2': '2x',
                '2.5': '2.5x',
                '3': '3x'
            }

            if multiplier is None or multiplier not in valid_values:
                embed = self.embed_builder.build_error(
                    title='Invalid Multiplier',
                    description='Please use one of the following valid multipliers:\n'
                                '`1`, `1.5`, `2`, `2.5`, `3`\n\nExample: `=booster 2.5`'
                )
                await ctx.reply(embed=embed)
                return

            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('booster', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            booster_value = multiplier
            existing_booster = self.db_manager.find_one('booster', {})

            if existing_booster:
                success = self.db_manager.update_one(
                    'booster',
                    {'_id': existing_booster['_id']},
                    {'$set': {'multiplier': booster_value}}
                )
            else:
                self.db_manager.insert('booster', {'multiplier': booster_value})
                success = True

            if success:
                embed = self.embed_builder.build_success(
                    title='Booster Set',
                    description=f'Successfully set the ELO and XP multiplier to **{value_name_map[booster_value]}**.\n'
                                f'This will affect all games until changed again.'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='Failed to set the booster. Please try again.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'booster command')
            try:
                embed = self.embed_builder.build_error(
                    description='An error occurred while setting the booster.'
                )
                await ctx.reply(embed=embed)
            except Exception as e:
                await self.error_handler.handle_error(e, 'booster command response')

async def setup(bot):
    await bot.add_cog(BoosterCommand(bot))
