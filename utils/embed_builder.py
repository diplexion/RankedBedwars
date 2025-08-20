import discord
from typing import Optional
import yaml
import os

class EmbedBuilder:
    def __init__(self):
        
        self.colors = {
            'success': 0x2ecc71,  
            'warning': 0xf1c40f,  
            'error': 0xe74c3c,    
            'info': 0x3498db      
        }

        
        self.icons = {
            'success': '✅',
            'warning': '⚠️',
            'error': '❌',
            'info': ' '
        }

        
        self.server_name = self.load_server_name()

    def load_server_name(self) -> str:
        config_path = os.path.join('configs', 'config.yml')
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config.get('server', {}).get('servername', 'Ranked Bedwars')
        except Exception as e:
            print(f"Failed to load server name: {e}")
            return "Ranked Bedwars"

    def _build_base_embed(self,
                     title: Optional[str] = None,
                     description: Optional[str] = None,
                     color: int = 0x000000,
                     icon: str = '',
                     footer_text: Optional[str] = None,
                     thumbnail_url: Optional[str] = None,
                     image_url: Optional[str] = None,
                     author_name: Optional[str] = None,
                     author_icon_url: Optional[str] = None,
                     fields: Optional[list[tuple[str, str, bool]]] = None) -> discord.Embed:
        embed = discord.Embed(color=color)

        if title:
            embed.title = f'{icon} {title}' if icon else title

        if description:
            embed.description = f"{description}"

        if footer_text:
            embed.set_footer(text=footer_text)

        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if image_url:
            embed.set_image(url=image_url)

        
        if not author_name:
            author_name = self.server_name

        embed.set_author(name=author_name, icon_url=author_icon_url if author_icon_url else None)

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        return embed

    def build_success(self,
                      title: str = 'Success',
                      description: Optional[str] = None,
                      **kwargs) -> discord.Embed:
        return self._build_base_embed(
            title=title,
            description=description,
            color=self.colors['success'],
            icon=self.icons['success'],
            author_name=self.server_name,  
            **kwargs
        )

    def build_warning(self,
                      title: str = 'Warning',
                      description: Optional[str] = None,
                      **kwargs) -> discord.Embed:
        return self._build_base_embed(
            title=title,
            description=description,
            color=self.colors['warning'],
            icon=self.icons['warning'],
            author_name=self.server_name,  
            **kwargs
        )

    def build_error(self,
                    title: str = 'Error',
                    description: Optional[str] = None,
                    **kwargs) -> discord.Embed:
        return self._build_base_embed(
            title=title,
            description=description,
            color=self.colors['error'],
            icon=self.icons['error'],
            author_name=self.server_name,  
            **kwargs
        )

    def build_info(self,
                   title: str = 'Information',
                   description: Optional[str] = None,
                   **kwargs) -> discord.Embed:
        return self._build_base_embed(
            title=title,
            description=description,
            color=self.colors['info'],
            icon=self.icons['info'],
            author_name=self.server_name,  
            **kwargs
        )
