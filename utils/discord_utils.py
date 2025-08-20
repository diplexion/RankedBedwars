import discord
from discord.ext import commands

async def send_message(channel_id, content=None, embed=None, guild=None):
    channel = guild.get_channel(channel_id)
    if channel:
        await channel.send(content=content, embed=embed)
    else:
        print(f"Channel with ID {channel_id} not found.")

async def delete_channel(channel_id, guild):
    try:
        channel_id = int(channel_id)
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.delete()
            print(f"Deleted channel {channel.name} ({channel.id})")
        else:
            print(f"Channel with ID {channel_id} not found in guild {guild.name}")
    except Exception as e:
        print(f"Failed to delete channel {channel_id}: {e}")
