import discord
import yaml
from datetime import datetime
import io
import chat_exporter

async def create_transcript(bot, channel_id: int, title: str):
    try:
        
        with open('configs/config.yml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        
        source_channel = bot.get_channel(channel_id)
        if not source_channel:
            raise ValueError(f"Channel with ID {channel_id} not found")
            
        transcript_channel_id = config.get('channels', {}).get('transcripts')
        if not transcript_channel_id:
            raise ValueError("Transcript channel ID not configured")
            
        transcript_channel = bot.get_channel(int(transcript_channel_id))
        if not transcript_channel:
            raise ValueError(f"Transcript channel with ID {transcript_channel_id} not found")
        
        
        messages = []
        users = set()
        image_count = 0
        
        async for message in source_channel.history(limit=None, oldest_first=True):
            messages.append(message)
            users.add(message.author)
            
            image_count += len([a for a in message.attachments if a.content_type and 'image' in a.content_type])
            image_count += len([e for e in message.embeds if e.image or e.thumbnail])
        
        
        transcript = await chat_exporter.export(
            source_channel,
            limit=None,
            tz_info="UTC",
            military_time=True,
            bot=bot,
        )
        
        if transcript is None:
            return False
        
        transcript_file = discord.File(
            io.BytesIO(transcript.encode()),
            filename=f'transcript-{channel_id}.html'
        )
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Channel", value=source_channel.name, inline=True)
        embed.add_field(name="Users", value=str(len(users)), inline=True)
        embed.add_field(name="Messages", value=str(len(messages)), inline=True)
        embed.add_field(name="Images", value=str(image_count), inline=True)
        embed.set_footer(text=f"Transcript created at")
        
        
        await transcript_channel.send(
            embed=embed,
            file=transcript_file
        )
        
        return True
        
    except Exception as e:
        print(f"Error creating transcript: {e}")
        return False
