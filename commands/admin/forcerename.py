import discord
from discord.ext import commands
from managers.database_manager import DatabaseManager
from managers.permission_manager import PermissionManager
from utils.embed_builder import EmbedBuilder
from actions.fix import fix
import yaml

class ForceRename(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager()
        self.permission_manager = PermissionManager()
        self.embed_builder = EmbedBuilder()
        with open('configs/config.yml', 'r', encoding='utf-8') as file:
            self.config = yaml.safe_load(file)

    @commands.command(name='forcerename', help='Force rename a user: !forcerename @user NewIGN')
    async def force_rename(self, ctx: commands.Context, user: discord.User, new_ign: str):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.permission_manager.has_permission('forcerename', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        try:
            query = {'discordid': str(user.id)}
            player = self.db_manager.find_one('users', query)

            if not player:
                embed = self.embed_builder.build_error(
                    description=f'{user.mention} is not registered yet!'
                )
                await ctx.reply(embed=embed)
                return

            existing_ign = self.db_manager.find_one(
                'users', {'ign': {'$regex': f'^{new_ign}$', '$options': 'i'}}
            )
            if existing_ign and str(existing_ign.get('discordid')) != str(user.id):
                embed = self.embed_builder.build_error(
                    description=f'The IGN `{new_ign}` is already taken by another user.'
                )
                await ctx.reply(embed=embed)
                return

            
            old_ign = player.get('ign')
            update_result = self.db_manager.update_one(
                'users',
                {'discordid': str(user.id)},
                {'$set': {'ign': new_ign}},
                upsert=False
            )

            if hasattr(update_result, 'modified_count') and update_result.modified_count > 0:
                await fix(self.bot, str(user.id), self.config['bot']['guildid'])
                embed = self.embed_builder.build_success(
                    title='Rename Successful',
                    description=f'{user.mention} has been renamed to: {new_ign}'
                )
                await ctx.reply(embed=embed)
                
                try:
                    config = self.config
                    reg_log_channel_id = int(config.get('logging', {}).get('regandrename'))
                    reg_log_channel = self.bot.get_channel(reg_log_channel_id)
                    if reg_log_channel:
                        log_embed = discord.Embed(
                            title="Manual Force Rename",
                            color=discord.Color.orange()
                        )
                        log_embed.add_field(name="User", value=f"<@{user.id}> ({user.id})", inline=True)
                        log_embed.add_field(name="Old IGN", value=f"`{old_ign}`", inline=True)
                        log_embed.add_field(name="New IGN", value=f"`{new_ign}`", inline=True)
                        log_embed.add_field(name="Renamed By", value=f"<@{ctx.author.id}> ({ctx.author.id})", inline=True)
                        await reg_log_channel.send(embed=log_embed)
                except Exception as log_exc:
                    print(f"Failed to send regandrename log: {log_exc}")
            elif hasattr(update_result, 'matched_count') and update_result.matched_count == 0:
                embed = self.embed_builder.build_error(
                    description=f'No user found with Discord ID {user.id}.'
                )
                await ctx.reply(embed=embed)
            else:
                embed = self.embed_builder.build_error(
                    description='No changes were made. The IGN may already be set to this value.'
                )
                await ctx.reply(embed=embed)

        except Exception as e:
            await self.bot.error_handler.handle_error(e, 'force rename command')
            embed = self.embed_builder.build_error(
                description=f'An error occurred: {str(e)}'
            )
            await ctx.reply(embed=embed)

async def setup(bot):
    await bot.add_cog(ForceRename(bot))
