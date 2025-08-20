import discord
from discord.ext import commands
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from utils.error_handler import ErrorHandler

class AddEloCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        self.error_handler = ErrorHandler(bot)

    @commands.command(name='addelo', help='Add a new ELO role configuration.')
    async def addelo(
        self, ctx, 
        roleid: str, 
        rankname: str, 
        minelo: int, 
        maxelo: int, 
        winelo: int, 
        loselo: int, 
        mvpelo: int, 
        color: str = '#FFFFFF'
    ):
        try:
            user_roles = [role.id for role in ctx.author.roles]
            if not self.permission_manager.has_permission('addelo', user_roles):
                embed = self.embed_builder.build_error(
                    title='Permission Denied',
                    description='You do not have permission to use this command.'
                )
                await ctx.reply(embed=embed)
                return

            if any(arg is None for arg in [roleid, rankname, minelo, maxelo, winelo, loselo, mvpelo]):
                embed = self.embed_builder.build_error(
                    title='Missing Arguments',
                    description='Usage: `=addelo <roleid> <rankname> <minelo> <maxelo> <winelo> <loselo> <mvpelo> [color]`\n\n'
                                'Arguments:\n'
                                '• `roleid`: Discord role ID\n'
                                '• `rankname`: Display name for this rank\n'
                                '• `minelo`: Minimum ELO requirement\n'
                                '• `maxelo`: Maximum ELO limit\n'
                                '• `winelo`: ELO points for winning\n'
                                '• `loselo`: ELO points for losing\n'
                                '• `mvpelo`: Additional ELO points for MVP\n'
                                '• `color`: Role color in hex format (optional, default: #FFFFFF)\n\n'
                                'Example:\n`=addelo 123456789 Gold 1000 2000 25 -20 5 #FF0000`'
                )
                await ctx.reply(embed=embed)
                return

            if not color.startswith('#') or len(color) != 7 or not all(c in '0123456789ABCDEFabcdef' for c in color[1:]):
                embed = self.embed_builder.build_error(
                    description='Invalid color format. Please use hex color code (e.g., #FF0000). If not specified, white (#FFFFFF) will be used.'
                )
                await ctx.reply(embed=embed)
                return

            existing_role = self.bot.database_manager.find_one('elos', {'roleid': roleid})
            if existing_role:
                embed = self.embed_builder.build_error(
                    description=f'An ELO configuration for role {roleid} already exists.'
                )
                await ctx.reply(embed=embed)
                return

            if minelo >= maxelo:
                embed = self.embed_builder.build_error(
                    description='Minimum ELO must be less than maximum ELO.'
                )
                await ctx.reply(embed=embed)
                return

            document = {
                'roleid': str(roleid),
                'minelo': minelo,
                'maxelo': maxelo,
                'winelo': winelo,
                'loselo': loselo,
                'mvpelo': mvpelo,
                'color': color,
                'rankname': rankname
            }

            self.bot.database_manager.insert('elos', document)

            embed = self.embed_builder.build_success(
                title='ELO Configuration Added',
                description=f'Successfully added ELO configuration for role {roleid}\n'
                            f'ELO Range: `{minelo} - {maxelo}`\n'
                            f'Win/Loss/MVP ELO: `+{winelo}/{loselo}/{mvpelo}`\n'
                            f'Color: `{color}`\n'
                            f'Rank Name: `{rankname}`'
            )
            await ctx.reply(embed=embed)

        except Exception as e:
            await self.error_handler.handle_error(e, 'add elo configuration')
            embed = self.embed_builder.build_error(
                description='An error occurred while adding ELO configuration.'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(AddEloCommand(bot))
