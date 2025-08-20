import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from utils.embed_builder import EmbedBuilder
import yaml

class PartyInviteView(View):
    def __init__(self, party_manager, party_name: str, target_id: str):
        super().__init__(timeout=30)  
        self.party_manager = party_manager
        self.party_name = party_name
        self.target_id = target_id
        self.logger = party_manager.logger if hasattr(party_manager, 'logger') else print

    @discord.ui.button(label="Accept Invite", style=discord.ButtonStyle.green)
    async def accept_invite(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.target_id:
            await interaction.response.send_message("This invite is not for you!", ephemeral=False)
            return

        
        party = self.party_manager.get_party(self.party_name)
        if not party:
            await interaction.response.send_message("Failed to join the party - it no longer exists.", ephemeral=False)
            return

        
        existing_party = self.party_manager.get_party_by_member(self.target_id)
        if existing_party:
            await interaction.response.send_message("You are already in a party. Please leave your current party first.", ephemeral=False)
            return

        
        if len(party.get('members', [])) >= self.party_manager.config.get('party', {}).get('partysize', 4):
            await interaction.response.send_message("Failed to join the party - it is full.", ephemeral=False)
            return

        if self.party_manager.member_join(self.party_name, self.target_id):
            await interaction.response.send_message("You have joined the party!", ephemeral=False)
            button.disabled = True
            await interaction.message.edit(view=self)
        else:
            await interaction.response.send_message("Failed to join the party. An error occurred.", ephemeral=False)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        self.logger(f"Party invite for {self.party_name} expired.")
        
        await self.message.edit(content="The party invite has expired.", view=None)

class PartyCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.embed_builder = EmbedBuilder()
        self.logger = bot.logger if hasattr(bot, 'logger') else print

    @commands.group(name="party", invoke_without_command=True, aliases=['p'])
    async def party(self, ctx):
        await ctx.reply("Missing subcommand! Use `/help` for more info.", delete_after=5)

    @party.command(name="create")
    async def create(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'create', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        party_name = str(ctx.author.id)
        self.logger.info(f"Attempting to create party for user {party_name}")

        existing_party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if existing_party:
            self.logger.warning(f"Party already exists for user {party_name}")
            embed = self.embed_builder.build_warning(
                description="You already have a party."
            )
        else:
            if self.bot.party_manager.create_party(party_name, party_name):
                self.logger.info(f"Successfully created party for user {party_name}")
                embed = self.embed_builder.build_success(
                    description="Party created successfully."
                )
            else:
                self.logger.error(f"Failed to create party for user {party_name}")
                embed = self.embed_builder.build_error(
                    description="Failed to create a party."
                )
        await ctx.reply(embed=embed)

    @party.command(name="list", aliases=['l', 'info', 'members'])
    async def list_members(self, ctx, member: discord.Member = None):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'list', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        target = member if member else ctx.author
        self.logger.info(f"Attempting to list party for member {target.id}")

        party = self.bot.party_manager.get_party_by_member(str(target.id))
        if not party:
            self.logger.warning(f"No party found for member {target.id}")
            embed = self.embed_builder.build_warning(
                description=f"{target.mention} is not in a party."
            )
            await ctx.reply(embed=embed)
            return

        members = party.get('members', [])
        leader_id = party.get('leader')
        party_elo = party.get('elo', 0)
        is_private = party.get('is_private', True)
        creation_time = party.get('creation_time')
        party_size = len(members)

        self.logger.info(f"Found party for member {target.id} with {party_size} members")

        member_list = '\n - '.join([f"<@{m}>" for m in members if m != leader_id]) or "No one yet"
        privacy_status = "private" if is_private else "public"
        creation_time_str = f"<t:{creation_time.time}>" if creation_time else "Unknown"

        embed = self.embed_builder.build_info(
            title="Party Information",
            description=f"**Leader:** <@{leader_id}>\n"
                        f"**Members:**\n - {member_list}\n"
                        f"**Info:**\n"
                        f" -  Party Elo: {party_elo}\n"
                        f" -  Party Size: {party_size}\n"
                        f" -  Party Status: {privacy_status}\n"
                        f" -  Party Creation Time: {creation_time_str}"
        )
        await ctx.reply(embed=embed)

    @party.command(name="invite", aliases=['i', 'add'])
    async def invite(self, ctx, member: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'invite', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if party and party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can invite members."
            )
            await ctx.reply(embed=embed)
            return

        party_name = str(ctx.author.id)
        self.logger.info(f"Attempting to invite {member.id} to party {party_name}")

        if hasattr(self.bot.party_manager, 'is_in_ignore_list') and self.bot.party_manager.is_in_ignore_list(str(member.id), str(ctx.author.id)):
            self.logger.warning(f"User {member.id} has {ctx.author.id} in their ignore list")
            embed = self.embed_builder.build_error(
                description=f"{member.mention} has you in their party ignore list."
            )
            await ctx.reply(embed=embed)
            return

        if not party:
            self.logger.info(f"Creating new party for {party_name} during invite")
            if not self.bot.party_manager.create_party(party_name, party_name):
                self.logger.error(f"Failed to create party for {party_name} during invite")
                embed = self.embed_builder.build_error(
                    description="Failed to create a party."
                )
                await ctx.reply(embed=embed)
                return

        max_size = self.bot.party_manager.config.get('party', {}).get('partysize', 4)
        party = self.bot.party_manager.get_party(party_name)
        if party and len(party['members']) >= max_size:
            embed = self.embed_builder.build_error(
                description="Your party is full!"
            )
            await ctx.reply(embed=embed)
            return

        embed = self.embed_builder.build_info(
            title="Party Invite",
            description=f"You have been invited to join {ctx.author.mention}'s party!"
        )
        view = PartyInviteView(self.bot.party_manager, party_name, str(member.id))

        await ctx.reply(content=f"{member.mention}", embed=embed, view=view)
        self.logger.info(f"Sent party invite to {member.id} for party {party_name}")


    @party.command(name="kick", aliases=['k'])
    async def kick(self, ctx, member: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'kick', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            return await ctx.reply(embed=embed)

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can kick members."
            )
            return await ctx.reply(embed=embed)

        if self.bot.party_manager.kick_member(str(ctx.author.id), str(member.id)):
            embed = self.embed_builder.build_success(description=f"{member.mention} has been kicked from the party.")
        else:
            embed = self.embed_builder.build_error(description="Failed to kick member from the party.")
        await ctx.reply(embed=embed)

    @party.command(name="promote", aliases=['leader'])
    async def promote(self, ctx, member: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'promote', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            return await ctx.reply(embed=embed)

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can promote members."
            )
            return await ctx.reply(embed=embed)

        if self.bot.party_manager.promote_member(str(ctx.author.id), str(member.id)):
            embed = self.embed_builder.build_success(description=f"{member.mention} has been promoted to party leader.")
        else:
            embed = self.embed_builder.build_error(description="Failed to promote member to party leader.")
        await ctx.reply(embed=embed)

    @party.command(name="leave")
    async def leave(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'leave', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            return await ctx.reply(embed=embed)

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party:
            embed = self.embed_builder.build_error(description="You are not in a party.")
            return await ctx.reply(embed=embed)

        if str(ctx.author.id) == party['leader']:
            if self.bot.party_manager.disband_party(str(ctx.author.id)):
                embed = self.embed_builder.build_success(description="You have left the party and it has been disbanded.")
            else:
                embed = self.embed_builder.build_error(description="Failed to disband the party.")
        else:
            if self.bot.party_manager.leave_party(party['leader'], str(ctx.author.id)):
                embed = self.embed_builder.build_success(description="You have left the party.")
            else:
                embed = self.embed_builder.build_error(description="Failed to leave the party.")
        await ctx.reply(embed=embed)

    @party.command(name="disband")
    async def disband(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'disband', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            return await ctx.reply(embed=embed)

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(description="Only the party leader can disband the party.")
            return await ctx.reply(embed=embed)

        if self.bot.party_manager.disband_party(str(ctx.author.id)):
            embed = self.embed_builder.build_success(description="The party has been disbanded.")
        else:
            embed = self.embed_builder.build_error(description="Failed to disband the party.")
        await ctx.reply(embed=embed)

    @party.command(name="private", aliases=['priv'])
    async def set_private(self, ctx, is_private: bool):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'private', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can change party privacy settings."
            )
            await ctx.reply(embed=embed)
            return

        party_name = str(party['leader'])
        if self.bot.party_manager.set_party_private(party_name, is_private):
            status = "private" if is_private else "public"
            embed = self.embed_builder.build_success(
                description=f"The party is now {status}."
            )
        else:
            embed = self.embed_builder.build_error(
                description="Failed to change party privacy status."
            )
        await ctx.reply(embed=embed)

    @party.group()
    async def ignore(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply("Use: party ignore add/remove")

    @ignore.command(name='add')
    async def ignore_add(self, ctx, member: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'ignore_add', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        user_id = ctx.author.id
        if self.bot.party_manager.add_to_ignore_list(user_id, member.id):
            embed = self.embed_builder.build_success(
                description=f"{member.mention} has been added to your party ignore list."
            )
        else:
            embed = self.embed_builder.build_error(
                description="Failed to add the user to your party ignore list."
            )
        await ctx.reply(embed=embed)

    @ignore.command(name='remove')
    async def ignore_remove(self, ctx, member: discord.Member):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'ignore_remove', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        user_id = ctx.author.id
        if self.bot.party_manager.remove_from_ignore_list(user_id, member.id):
            embed = self.embed_builder.build_success(
                description=f"{member.mention} has been removed from your party ignore list."
            )
        else:
            embed = self.embed_builder.build_error(
                description="Failed to remove the user from your party ignore list."
            )
        await ctx.reply(embed=embed)

    @party.command(name="warp")
    async def warp(self, ctx):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'warp', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can warp members."
            )
            await ctx.reply(embed=embed)
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            embed = self.embed_builder.build_error(
                description="You must be in a voice channel to warp party members."
            )
            await ctx.reply(embed=embed)
            return

        target_channel = ctx.author.voice.channel
        cant_move = []

        for member_id in party.get('members', []):
            if member_id == str(ctx.author.id):
                continue

            member = ctx.guild.get_member(int(member_id))
            if member:
                try:
                    await member.move_to(target_channel)
                except:
                    cant_move.append(member.mention)

        if cant_move:
            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
            alerts_channel = self.bot.get_channel(int(config['channels']['alerts']))

            if alerts_channel:
                alert_embed = self.embed_builder.build_warning(
                    title="Party Warp Failed",
                    description=f"Could not move some party members to {target_channel.mention}"
                )
                await alerts_channel.send(
                    content=f"{ctx.author.mention} couldn't move: {', '.join(cant_move)}",
                    embed=alert_embed
                )

            response_embed = self.embed_builder.build_warning(
                description=f"Some members could not be warped. Check {alerts_channel.mention} for details."
            )
        else:
            response_embed = self.embed_builder.build_success(
                description=f"Successfully warped all party members to {target_channel.mention}"
            )

        await ctx.reply(embed=response_embed)

    @party.command(name="autowarp")
    async def autowarp(self, ctx, enabled: bool):
        user_roles = [role.id for role in ctx.author.roles]
        if not self.bot.permission_manager.has_group_permission('party', 'autowarp', user_roles):
            embed = self.embed_builder.build_error(
                title='Permission Denied',
                description='You do not have permission to use this command.'
            )
            await ctx.reply(embed=embed)
            return

        party = self.bot.party_manager.get_party_by_member(str(ctx.author.id))
        if not party or party.get('leader') != str(ctx.author.id):
            embed = self.embed_builder.build_error(
                description="Only the party leader can change autowarp settings."
            )
            await ctx.reply(embed=embed)
            return

        try:
            self.bot.database_manager.update_one(
                'parties',
                {'party_name': party['party_name']},
                {'$set': {'autopartywarp': enabled}}
            )

            embed = self.embed_builder.build_success(
                description=f"Auto party warp has been {'enabled' if enabled else 'disabled'}."
            )
            await ctx.reply(embed=embed)
        except Exception as e:
            embed = self.embed_builder.build_error(
                description=f"Failed to update autowarp settings: {str(e)}"
            )
            await ctx.reply(embed=embed)

def setup(bot):
    bot.add_cog(PartyCommands(bot))
