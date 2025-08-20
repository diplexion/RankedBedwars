import discord
from discord.ext import commands
from actions.fix import fix  
from managers.database_manager import DatabaseManager
from utils.embed_builder import EmbedBuilder
import yaml

class GuildJoinListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.config = self.load_config()

    def load_config(self):
        with open('configs/config.yml', 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        db_manager = DatabaseManager()
        try:
            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            user = db_manager.find_one('users', {'discordid': str(member.id)})
            alerts_channel_id = self.config['channels']['alerts']
            alerts_channel = self.bot.get_channel(alerts_channel_id)
            if user:
                ign = user.get('ign', member.name)
                await alerts_channel.send(f"Hey {member.mention}, welcome back! it's not the first time I'm seeing you here. Let me fix your stuff and get you ready to queue some sweaty games!")
                guild_id = config['bot']['guildid']
                fix(self.bot, member.id, guild_id)
                self.bot.logger.info(f"Called fix function for user {member.id}")
            else:
                unregistered_role_id = self.config['roles']['unregistered']
                unregistered_role = member.guild.get_role(unregistered_role_id)
                if unregistered_role:
                    await member.add_roles(unregistered_role)
                    self.bot.logger.info(f"Added unregistered role to new user {member.id}")
                else:
                    self.bot.logger.error(f"Unregistered role {unregistered_role_id} not found")
        except Exception as e:
            self.bot.logger.error(f"Error processing member join for user {member.id}: {e}")
        finally:
            db_manager.close()

async def setup(bot):
    await bot.add_cog(GuildJoinListener(bot))
