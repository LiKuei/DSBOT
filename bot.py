import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

# 載入環境變量
load_dotenv()

# 設定 FFmpeg 路徑 (如果不在系統 PATH 中)
FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': 'True',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'extract_flat': False,
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-us,en;q=0.5',
        'Sec-Fetch-Mode': 'navigate',
    }
}

# 從環境變量獲取 Token
TOKEN = os.getenv('DISCORD_TOKEN')

# 指令前綴
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 音樂隊列
music_queues = {}

@bot.event
async def on_ready():
    print(f'{bot.user.name} 已經上線了！')

@bot.command(name='play', help='播放 YouTube 音樂')
async def play(ctx, *, search_query: str):
    if not ctx.author.voice:
        await ctx.send("你需要先加入一個語音頻道！")
        return

    voice_channel = ctx.author.voice.channel
    
    if not ctx.voice_client:
        await voice_channel.connect()
    elif ctx.voice_client.channel != voice_channel:
        await ctx.voice_client.move_to(voice_channel)

    # 初始化該伺服器的隊列
    if ctx.guild.id not in music_queues:
        music_queues[ctx.guild.id] = []

    async with ctx.typing():
        try:
            with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                if "youtube.com/watch?v=" in search_query or "youtu.be/" in search_query:
                    info = ydl.extract_info(search_query, download=False)
                else:
                    info = ydl.extract_info(f"ytsearch:{search_query}", download=False)['entries'][0]

                url = info['url']
                title = info.get('title', '未知歌曲')
                
                # 將歌曲加入隊列
                music_queues[ctx.guild.id].append({
                    'url': url,
                    'title': title
                })
                
                await ctx.send(f'🎧 已將 **{title}** 加入隊列')
                
                # 如果沒有正在播放的音樂，開始播放
                if not ctx.voice_client.is_playing():
                    await play_next(ctx)

        except Exception as e:
            await ctx.send(f"播放時發生錯誤：{str(e)}")
            print(f"Error in play command: {e}")

async def play_next(ctx):
    if not music_queues[ctx.guild.id]:
        return

    try:
        song = music_queues[ctx.guild.id][0]
        source = await discord.FFmpegOpusAudio.from_probe(song['url'], **FFMPEG_OPTIONS)
        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f'🎧 正在播放: **{song["title"]}**')
        music_queues[ctx.guild.id].pop(0)
    except Exception as e:
        await ctx.send(f"播放下一首歌曲時發生錯誤：{str(e)}")
        print(f"Error in play_next: {e}")

@bot.command(name='skip', help='跳過當前歌曲')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ 已跳過當前歌曲")
    else:
        await ctx.send("目前沒有正在播放的歌曲")

@bot.command(name='queue', help='顯示播放隊列')
async def queue(ctx):
    if not music_queues[ctx.guild.id]:
        await ctx.send("目前播放隊列是空的")
        return

    queue_list = "\n".join([f"{i+1}. {song['title']}" for i, song in enumerate(music_queues[ctx.guild.id])])
    await ctx.send(f"📋 播放隊列：\n{queue_list}")

@bot.command(name='leave', help='讓機器人離開語音頻道')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if ctx.guild.id in music_queues:
            music_queues[ctx.guild.id].clear()
        await ctx.send("我已經離開語音頻道。")
    else:
        await ctx.send("我目前不在任何語音頻道中。")

if __name__ == "__main__":
    if not TOKEN:
        print("錯誤：未找到 DISCORD_TOKEN 環境變量")
        exit(1)
    bot.run(TOKEN)