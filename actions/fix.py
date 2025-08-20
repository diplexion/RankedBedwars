
import yaml
import discord
import asyncio
import re
from managers.database_manager import DatabaseManager
from managers.workermanager import WorkerManager

def extract_role_id(raw_id):
    if isinstance(raw_id, int):
        return raw_id
    if isinstance(raw_id, str):
        match = re.match(r'<@&(\d+)>', raw_id)
        if match:
            return int(match.group(1))
        try:
            return int(raw_id)
        except Exception:
            pass
    raise ValueError(f"Invalid roleid: {raw_id}")

async def update_member_roles(member, roles_to_add, roles_to_remove, reason):
    
    
    worker_manager = getattr(getattr(member, 'bot', None), 'worker_manager', None)
    if worker_manager and worker_manager.enabled:
        try:
            
            bot = worker_manager.worker_bots[0] if worker_manager.worker_bots else None
            if bot:
                guild = discord.utils.get(bot.guilds, id=member.guild.id)
                worker_member = guild.get_member(member.id) if guild else None
                if worker_member:
                    if roles_to_remove:
                        await worker_member.remove_roles(*roles_to_remove, reason=reason)
                    if roles_to_add:
                        await worker_member.add_roles(*roles_to_add, reason=reason)
                    return
        except Exception as e:
            print(f"[workerbot] Error updating roles for user {member.id}: {e}")
    
    try:
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=reason)
        if roles_to_add:
            await member.add_roles(*roles_to_add, reason=reason)
    except Exception as e:
        print(f"Error updating roles for user {member.id}: {e}")

async def reset_member_nickname(member, reason):
    
    worker_manager = getattr(getattr(member, 'bot', None), 'worker_manager', None)
    if worker_manager and worker_manager.enabled:
        try:
            bot = worker_manager.worker_bots[0] if worker_manager.worker_bots else None
            if bot:
                guild = discord.utils.get(bot.guilds, id=member.guild.id)
                worker_member = guild.get_member(member.id) if guild else None
                if worker_member:
                    await asyncio.wait_for(worker_member.edit(nick="", reason=reason), timeout=5.0)
                    return
        except Exception as e:
            print(f"[workerbot] Error resetting nickname for user {member.id}: {e}")
    try:
        await asyncio.wait_for(member.edit(nick="", reason=reason), timeout=5.0)
    except asyncio.TimeoutError:
        print(f"Timeout while resetting nickname for user {member.id}")
    except discord.errors.Forbidden:
        print(f"No permission to reset nickname for user {member.id}")
    except Exception as e:
        print(f"Error resetting nickname for user {member.id}: {e}")

async def update_member_nickname(member, new_nick, reason):
    
    worker_manager = getattr(getattr(member, 'bot', None), 'worker_manager', None)
    if worker_manager and worker_manager.enabled:
        try:
            bot = worker_manager.worker_bots[0] if worker_manager.worker_bots else None
            if bot:
                guild = discord.utils.get(bot.guilds, id=member.guild.id)
                worker_member = guild.get_member(member.id) if guild else None
                if worker_member:
                    await asyncio.wait_for(worker_member.edit(nick=new_nick, reason=reason), timeout=5.0)
                    return
        except Exception as e:
            print(f"[workerbot] Error updating nickname for user {member.id}: {e}")
    try:
        await asyncio.wait_for(member.edit(nick=new_nick, reason=reason), timeout=5.0)
    except asyncio.TimeoutError:
        print(f"Timeout while updating nickname for user {member.id}")
    except discord.errors.Forbidden:
        print(f"No permission to update nickname for user {member.id}")
    except Exception as e:
        print(f"Error updating nickname for user {member.id}: {e}")

async def fix(bot, discordid, guild_id):
    db_manager = DatabaseManager()
    
    guild = bot.get_guild(int(guild_id))
    try:
        try:
            guild = bot.get_guild(int(guild_id))
        except Exception as e:
            print(f"[fix] Invalid guild_id {guild_id}: {e}")
            return
        if not guild:
            print(f"[fix] Guild with ID {guild_id} not found.")
            return
        try:
            member = guild.get_member(int(discordid))
        except Exception as e:
            print(f"[fix] Invalid discordid {discordid}: {e}")
            return
        if not member:
            print(f"[fix] User with ID {discordid} not found in guild {guild_id}.")
            return

        try:
            with open('configs/config.yml', 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
        except Exception as e:
            print(f"[fix] Failed to load config: {e}")
            return

        try:
            user = db_manager.find_one('users', {'discordid': str(discordid)})
        except Exception as e:
            print(f"[fix] DB error fetching user: {e}")
            user = None
        try:
            elos = db_manager.find('elos', {})
        except Exception as e:
            print(f"[fix] DB error fetching elos: {e}")
            elos = []
        try:
            elo_role_ids = [extract_role_id(elo_entry['roleid']) for elo_entry in elos]
        except Exception as e:
            print(f"[fix] Error extracting ELO role IDs: {e}")
            elo_role_ids = []
        try:
            current_roles = set(role.id for role in getattr(member, 'roles', []))
        except Exception as e:
            print(f"[fix] Error getting member roles: {e}")
            current_roles = set()

        try:
            registered_role_id = int(config['roles']['registered'])
            unregistered_role_id = int(config['roles']['unregistered'])
        except Exception as e:
            print(f"[fix] Error reading role IDs from config: {e}")
            return
        registered_role = discord.Object(id=registered_role_id)
        unregistered_role = discord.Object(id=unregistered_role_id)

        if user is None:
            
            roles_to_remove = [discord.Object(id=rid) for rid in current_roles if rid == registered_role_id or rid in elo_role_ids]
            roles_to_add = []
            if unregistered_role_id not in current_roles:
                roles_to_add.append(unregistered_role)
            try:
                await update_member_roles(member, roles_to_add, roles_to_remove, "Unregistered user role fix")
            except Exception as e:
                print(f"[fix] Error updating roles for unregistered user {discordid}: {e}")
            try:
                await reset_member_nickname(member, "Reset nickname for unregistered user")
            except Exception as e:
                print(f"[fix] Error resetting nickname for unregistered user {discordid}: {e}")
            return

        
        try:
            settings = db_manager.find_one('settings', {'discordid': str(discordid)})
        except Exception as e:
            print(f"[fix] DB error fetching settings: {e}")
            settings = None
        if settings is None:
            settings = {
                'discordid': str(discordid),
                'isprefixtoggled': False,
                'ispartyinvitestoggled': False,
                'isscoringpingtoggled': False,
                'staticnickname': False,
                'nickname': ''
            }
            try:
                db_manager.insert('settings', settings)
            except Exception as e:
                print(f"[fix] DB error inserting default settings: {e}")

        roles_to_add = []
        roles_to_remove = []
        if unregistered_role_id in current_roles:
            roles_to_remove.append(unregistered_role)
        if registered_role_id not in current_roles:
            roles_to_add.append(registered_role)
        try:
            await update_member_roles(member, roles_to_add, roles_to_remove, "Role fix update")
        except Exception as e:
            print(f"[fix] Error updating registered/unregistered roles for {discordid}: {e}")

        elo = user.get('elo', 0) if isinstance(user, dict) else 0
        ign = user.get('ign', '') if isinstance(user, dict) else ''
        nickname = settings.get('nickname', '') if isinstance(settings, dict) else ''
        is_prefix_toggled = settings.get('isprefixtoggled', False) if isinstance(settings, dict) else False
        static_nickname_enabled = settings.get('staticnickname', False) if isinstance(settings, dict) else False

        try:
            if static_nickname_enabled:
                await reset_member_nickname(member, "Static nickname enabled")
            else:
                if is_prefix_toggled:
                    new_nickname = f"{ign} | {nickname}".strip() if nickname else ign
                else:
                    new_nickname = f"[{elo}] {ign} | {nickname}".strip() if nickname else f"[{elo}] {ign}"
                await update_member_nickname(member, new_nickname, "Nickname fix update")
        except Exception as e:
            print(f"[fix] Error updating nickname for {discordid}: {e}")

        
        correct_role = None
        try:
            for elo_entry in elos:
                try:
                    minelo = elo_entry.get('minelo', float('-inf'))
                    maxelo = elo_entry.get('maxelo', float('inf'))
                    roleid = extract_role_id(elo_entry['roleid'])
                except Exception as e:
                    print(f"[fix] Error parsing elo_entry: {e}")
                    continue
                if minelo <= elo <= maxelo:
                    correct_role = discord.Object(id=roleid)
                    break
        except Exception as e:
            print(f"[fix] Error determining correct ELO role: {e}")
        roles_to_add = []
        roles_to_remove = []
        if correct_role and correct_role.id not in current_roles:
            roles_to_add.append(correct_role)
        for role_id in elo_role_ids:
            if role_id in current_roles and (not correct_role or role_id != correct_role.id):
                roles_to_remove.append(discord.Object(id=role_id))
        try:
            await update_member_roles(member, roles_to_add, roles_to_remove, "ELO role fix update")
        except Exception as e:
            print(f"[fix] Error updating ELO roles for {discordid}: {e}")
    except Exception as e:
        print(f'[fix] Unexpected error fixing user {discordid}: {e}')
    finally:
        try:
            db_manager.close()
        except Exception as e:
            print(f"[fix] Error closing DB manager: {e}")
