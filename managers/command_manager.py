import os
import importlib.util
import yaml
from typing import Optional
from discord.ext import commands
import discord
import inspect
from discord import app_commands

class CommandManager:
    def __init__(self, bot):
        self.bot = bot
        self.commands_dir = 'commands'
        self.permissions_file = 'configs/permissions.yml'
        self.permissions = self.load_permissions()
        self.loaded_commands = set()

        self.bot.add_check(self._commands_channel_only_check)

    async def _commands_channel_only_check(self, ctx):
        try:
            channel_id = int(self.bot.config['channels']['commandschannel'])
            blocked_channels = set()
            blocked_list = self.bot.config.get('commandsblocked', [])
            for ch in blocked_list:
                try:
                    blocked_channels.add(int(ch))
                except Exception:
                    pass
        except Exception:
            return True

        
        if ctx.channel.id in blocked_channels:
            try:
                reply = await ctx.reply(":x: Commands are blocked in this channel.", mention_author=False)
                await self._delete_after(ctx.message, reply, delay=15)
            except Exception as e:
                self.bot.logger.error(f"Failed to send/delete command block warning: {e}")
            return False

        return True

    async def _delete_after(self, command_message, reply_message, delay=15):
        import asyncio
        await asyncio.sleep(delay)
        try:
            await command_message.delete()
        except Exception:
            pass
        try:
            await reply_message.delete()
        except Exception:
            pass

    def load_permissions(self) -> dict:
        try:
            if os.path.exists(self.permissions_file):
                with open(self.permissions_file, 'r') as file:
                    permissions = yaml.safe_load(file)
                    if permissions:
                        return permissions
            
            self.permissions = {}
            self.save_permissions()
            return {}
        except Exception as e:
            self.bot.logger.error(f'Failed to load permissions: {e}')
            return {}

    def save_permissions(self):
        try:
            
            os.makedirs(os.path.dirname(self.permissions_file), exist_ok=True)
            
            with open(self.permissions_file, 'w') as file:
                yaml.dump(self.permissions, file, default_flow_style=False)
            self.bot.logger.info(f'Saved permissions to {self.permissions_file}')
        except Exception as e:
            self.bot.logger.error(f'Failed to save permissions: {e}')

    async def load_commands(self) -> None:
        await self.load_command_modules(self.commands_dir)

    

    
    def extract_command_names(self, module_or_cog):
        command_names = []
        for attr_name in dir(module_or_cog):
            attr = getattr(module_or_cog, attr_name)
            if isinstance(attr, commands.Command):
                command_names.append(attr.name)
        return command_names

    

    async def load_command_modules(self, directory: str) -> None:
        if not os.path.exists(directory):
            os.makedirs(directory)
            return

        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py') and not file.startswith('_'):
                    try:
                        file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(file_path, start=os.getcwd())
                        module_path = os.path.splitext(relative_path)[0].replace(os.sep, '.')


                        spec = importlib.util.spec_from_file_location(module_path, file_path)
                        if spec and spec.loader:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)

                            
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if isinstance(attr, type) and issubclass(attr, commands.Cog) and attr != commands.Cog:
                                    try:
                                        if attr_name in self.bot.cogs:
                                            continue
                                        cog_instance = attr(self.bot)
                                        cog_commands = self.extract_command_names(cog_instance)
                                        await self.bot.add_cog(cog_instance)
                                        self.loaded_commands.update(cog_commands)
                                    except Exception as e:
                                        import traceback
                                        self.bot.logger.error(traceback.format_exc())
                            
                            for attr_name in dir(module):
                                attr = getattr(module, attr_name)
                                if isinstance(attr, commands.Command):
                                    try:
                                        await self.bot.add_command(attr)
                                        self.loaded_commands.add(attr.name)
                                    except Exception as e:
                                        import traceback
                                        self.bot.logger.error(traceback.format_exc())
                    except Exception as e:
                        import traceback
                        self.bot.logger.error(traceback.format_exc())

    async def reload_all_commands(self) -> None:
        try:
            for name in list(self.bot.cogs.keys()):
                await self.bot.remove_cog(name)
            
            
            self.loaded_commands.clear()
            
            await self.load_commands()
        except Exception as e:
            import traceback
            self.bot.logger.error(traceback.format_exc())

    def get_command(self, command_name: str) -> Optional[commands.Command]:
        command = self.bot.get_command(command_name)
        if command:
            async def disabled_command(ctx):
                await ctx.reply(":x: The message commands are disabled. Use `=help` to continue.")
            command.callback = disabled_command
        return command

    def get_all_commands(self) -> list[commands.Command]:
        return list(self.bot.commands)

    async def reload_command(self, command_name: str) -> bool:
        command = self.get_command(command_name)
        if not command:
            return False

        try:
            await self.bot.reload_extension(command.module)
            return True
        except Exception as e:
            self.bot.logger.error(f'Failed to reload command {command_name}: {e}')
            return False
