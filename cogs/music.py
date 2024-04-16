import asyncio
import json
from typing import Any
from urllib import parse

import discord
from discord import app_commands
from discord.ext import commands

import yt_dlp


class PlayButton(discord.ui.Button):
    def __init__(self, guild: discord.Guild):
        super().__init__(row=0)
        self.set_emoji(guild)

    def set_emoji(self, guild: discord.Guild | None):
        if guild.voice_client is not None and guild.voice_client.is_connected() and guild.voice_client.is_playing():
            self.emoji = '⏸️'
        else:
            self.emoji = '▶️'

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
        elif interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
        else:
            self.view.play_song(interaction)

        self.set_emoji(interaction.guild)
        MusicPlayer.set_embed_title(interaction.guild)
        MusicPlayer.set_embed_author(interaction.user)
        MusicPlayer.set_embed_attributes(interaction.user)
        await interaction.response.edit_message(embed=MusicPlayer.embed, view=self.view)


class SkipButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji='⏭️', row=0)

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.stop()
        else:
            self.view.play_after(None, interaction)


class RepeatButton(discord.ui.Button):
    def __init__(self):
        super().__init__(row=0)
        self.set_emoji()

    def set_emoji(self):
        self.emoji = MusicPlayer.repeat_dict.get(MusicPlayer.repeat)

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        MusicPlayer.repeat = (MusicPlayer.repeat + 1) % 3

        self.set_emoji()
        MusicPlayer.set_embed_author(interaction.user)
        MusicPlayer.set_embed_attributes(interaction.user)
        await interaction.response.edit_message(embed=MusicPlayer.embed, view=self.view)


class SearchModal(discord.ui.Modal):
    keyword = discord.ui.TextInput(
        label='검색어',
        placeholder='검색어를 입력해요',
        required=False,
        row=0
    )
    url = discord.ui.TextInput(
        label='URL',
        placeholder='URL을 입력해요',
        required=False,
        row=1
    )

    def __init__(self):
        super().__init__(title='노래 가져오기 🎹🔍')

    async def interaction_check(self, interaction: discord.Interaction):
        return len(self.keyword.value) or len(self.url.value)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if len(self.keyword.value):
            await MusicPlayer.load_yt_search_info(interaction, self.keyword.value)
        if len(self.url.value):
            query_str_dict = parse.parse_qs(parse.urlparse(self.url.value).query)
            if 'list' in query_str_dict:
                await MusicPlayer.load_yt_playlist_info(interaction, query_str_dict.get('list')[0])
            elif 'v' in query_str_dict:
                await MusicPlayer.load_yt_song_info(interaction, query_str_dict.get('v')[0])
            else:
                print('SearchModal:on_submit: invalid youtube url')


class SearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji='🔍', row=0)

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal())
        MusicPlayer.set_embed_author(interaction.user)
        MusicPlayer.set_embed_attributes(interaction.user)
        await interaction.edit_original_response(embed=MusicPlayer.embed)
        print(2)


class MusicPlayer(discord.ui.View):
    history: list[dict[str, str | int]] = []
    playlist: list[dict[str, str | int]] = []
    cmd_msg: discord.Message
    sended_msg: discord.Message = None
    volume = 0.1
    repeat = 0
    repeat_dict = {0: '⏯️', 1: '🔁', 2: '🔂'}
    embed: discord.Embed = discord.Embed(color=discord.Color.blurple())
    ytdlp = yt_dlp.YoutubeDL({
        'format': 'bestaudio/best',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        #'logtostderr': False,
        #'quiet': True,
        #'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'extract_flat': True,
        'skip_download': True,
    })
    embed_batch_size = 10
    index_emoji_dict = {'1️⃣': 0, '2️⃣': 1, '3️⃣': 2, '4️⃣': 3, '5️⃣': 4, '6️⃣': 5, '7️⃣': 6, '8️⃣': 7, '9️⃣': 8, '🔟': 9}
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def set_embed_title(cls, guild: discord.Guild):
        if guild.voice_client is not None and guild.voice_client.is_connected():
            if guild.voice_client.is_playing():
                cls.embed.title = '▶️  재생 중'
            elif guild.voice_client.is_paused():
                cls.embed.title = '⏸️  일시 정지'
            else:
                cls.embed.title = '⏹️  대기 중'
        else:
            cls.embed.title = '⏹️  대기 중'

        cls.embed.title = cls.embed.title + f'  -  음량 {int(cls.volume * 100)}%'

    @classmethod
    def set_embed_author(cls, author: discord.User | discord.Member):
        cls.embed.set_footer(text=author, icon_url=author.display_avatar.url)

    @classmethod
    def set_embed_attributes(cls, author: discord.User | discord.Member):
        cls.embed.clear_fields()
        cls.embed.add_field(name='', value='', inline=False)

        if cls.playlist:
            cls.embed.set_thumbnail(url=cls.playlist[0]['thumbnail'])
            cls.embed.description = f'[{cls.playlist[0]['title']}]({cls.playlist[0]['url']}) [{cls.convert_seconds(cls.playlist[0]['length'])}]\n\n{cls.playlist[0].get('artist') if 'artist' in cls.playlist[0] else ''}'

            for i in range(0, len(cls.playlist), cls.embed_batch_size):
                cls.embed.add_field(
                    name='[Playlist]' if i == 0 else '',
                    value='\n'.join([f'{i + j + 1}. [{song.get("title")}]({song.get("url")}) [{cls.convert_seconds(song.get("length"))}]' for j, song in enumerate(cls.playlist[i:min(i + cls.embed_batch_size, len(cls.playlist))])]),
                    inline=False
                )
        else:
            cls.embed.set_thumbnail(url=author.display_avatar.url)
            cls.embed.description = '재생할 수 있는 노래가 없어요 ㅠ-ㅠ\n\n플레이리스트에 노래를 추가해야 해요'
            cls.embed.add_field(name='[Playlist]', value='비어있어요...', inline=False)

    @classmethod
    async def from_message(cls, message: discord.Message):
        if cls.sended_msg is not None:
            await cls.sended_msg.delete()
        cls.cmd_msg = message
        music_player = cls()
        play_button = PlayButton(message.guild)
        skip_button = SkipButton()
        repeat_button = RepeatButton()
        search_button = SearchButton()
        music_player.add_item(play_button)
        music_player.add_item(skip_button)
        music_player.add_item(repeat_button)
        music_player.add_item(search_button)
        MusicPlayer.set_embed_author(message.author)
        MusicPlayer.set_embed_title(message.guild)
        MusicPlayer.set_embed_attributes(message.author)
        cls.sended_msg = await message.channel.send(embed=MusicPlayer.embed, view=music_player)
        return music_player

    def play_song(self, interaction: discord.Interaction):
        if MusicPlayer.playlist:
            interaction.guild.voice_client.play(
                source=discord.PCMVolumeTransformer(
                    original=discord.FFmpegPCMAudio(
                        source=MusicPlayer.playlist[0]['source'],
                        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                        options='-vn',
                    ),
                    volume=MusicPlayer.volume,
                ),
                after=lambda e: self.play_after(e, interaction),
                bitrate=512,
                expected_packet_loss=0.01,
                signal_type='music',
            )
        else:
            print('play_song: MusicPlayer.playlist is empty')

        self.children[0].set_emoji(interaction.guild)
        MusicPlayer.set_embed_title(interaction.guild)
        MusicPlayer.set_embed_attributes(interaction.user)
        MusicPlayer.set_embed_author(interaction.user)
        asyncio.run_coroutine_threadsafe(MusicPlayer.sended_msg.edit(embed=MusicPlayer.embed, view=self), Music.bot.loop)

    def play_after(self, error: Exception | None, interaction: discord.Interaction):
        if error:
            print(f'MusicPlayer:play_after: {error}')
        if MusicPlayer.playlist:
            if MusicPlayer.repeat == 0:
                del MusicPlayer.playlist[0]
            elif MusicPlayer.repeat == 1 or MusicPlayer.repeat == 2:
                MusicPlayer.playlist.append(MusicPlayer.playlist.pop(0))
            else:
                print('MusicPlayer:play_after: not cls.repeat == 0 and not cls.repeat == 1 and not cls.repeat == 2')
                
            self.play_song(interaction)
        else:
            self.children[0].set_emoji(interaction.guild)
            MusicPlayer.set_embed_title(interaction.guild)
            MusicPlayer.set_embed_attributes(interaction.user)
            MusicPlayer.set_embed_author(interaction.user)
            asyncio.run_coroutine_threadsafe(MusicPlayer.sended_msg.edit(embed=MusicPlayer.embed, view=self), Music.bot.loop)
            print('MusicPlayer:play_after: cls.playlist is empty')

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.voice is not None:
            if interaction.guild.voice_client is None or not interaction.guild.voice_client.is_connected():
                await interaction.user.voice.channel.connect(timeout=1.5)
                return True
            if interaction.user.voice.channel == interaction.guild.voice_client.channel:
                return True
            elif not interaction.guild.voice_client.is_playing():
                await interaction.guild.voice_client.move_to(interaction.user.voice.channel, timeout=1.5)
                return True

        await interaction.response.edit_message(view=self)
        return False
    
    @staticmethod
    def parse_yt_url(url: str):
        url_dict = parse.parse_qs(parse.urlparse(url).query)
        if 'list' in url_dict:
            if url_dict['list']:
                return url_dict['list'][0]
            else:
                print('stream_yt_url: url_dict["list"] is empty')
        elif 'v' in url_dict:
            if url_dict['v']:
                return url_dict['v'][0]
            else:
                print('stream_yt_url: url_dict["v"] is empty')
        else:
            print('stream_yt_url: url is None')

    @classmethod
    async def load_yt_playlist_info(cls, interaction: discord.Interaction, id: str):
        info = await Music.bot.loop.run_in_executor(None, cls.ytdlp.extract_info, 'https://music.youtube.com/playlist?list=' + id, False)
        if info is not None:
            if 'entries' in info:
                for song in info['entries']:
                    if 'id' in song:
                        await cls.load_yt_song_info(interaction, song['id'])
                    else:
                        print(f'load_yt_playlist_info: not "id" in song')
                return
            else:
                print('load_yt_playlist_info: not "entries" in info')
        else:
            print('load_yt_playlist_info: info is None')

    @classmethod
    async def load_yt_song_info(cls, interaction: discord.Interaction, id: str):
        for song in cls.history:
            if song.get('id') == id:
                cls.playlist.append(song)
                cls.set_embed_author(interaction.user)
                cls.set_embed_title(interaction.guild)
                cls.set_embed_attributes(interaction.user)
                await cls.sended_msg.edit(embed=cls.embed)
                print(f'load_yt_song_info: Append {song.get('title')} in self.history to self.playlist')
                return

        info = await Music.bot.loop.run_in_executor(None, cls.ytdlp.extract_info, 'https://music.youtube.com/watch?v=' + id, False)
        if info is not None:
            if 'id' in info and 'duration' in info and 'url' in info and 'thumbnail' in info and 'thumbnails' in info and 'title' in info and 'webpage_url' in info:
                song = {
                    'id': info['id'],
                    'length': info['duration'],
                    'source': info['url'],
                    'title': info['title'],
                    'url': info['webpage_url']
                }
                square_thumbnail = cls.get_square_thumbnail(info['thumbnails'])
                if square_thumbnail is not None:
                    song['thumbnail'] = square_thumbnail
                else:
                    song['thumbnail'] = info['thumbnail']
                if 'artist' in info:
                    song['artist'] = info['artist']
                else:
                    print('load_yt_song_info: not "artist" in info')
                cls.history.append(song)
                cls.playlist.append(song)
                cls.set_embed_author(interaction.user)
                cls.set_embed_title(interaction.guild)
                cls.set_embed_attributes(interaction.user)
                await cls.sended_msg.edit(embed=cls.embed)
            else:
                print('load_yt_song_info: not "id" or "duration" or "url" or "thumbnail" or "thumbnails" or "title" or "webpage_url" in info')
        else:
            print('load_yt_song_info: info is None')

    @staticmethod
    def get_square_thumbnail(thumbnails: list[dict[str, Any]]):
        max_res_square = 0
        max_res_square_thumbnail = None

        for thumbnail in thumbnails:
            height = thumbnail.get('height')
            width = thumbnail.get('width')
            url = thumbnail.get('url')
            if height is not None and width is not None and url is not None:
                if height == width and height > max_res_square:
                    max_res_square = height
                    max_res_square_thumbnail = url
        return max_res_square_thumbnail

    @classmethod
    async def load_yt_search_info(cls, interaction: discord.Interaction, keyword: str):
        info = await Music.bot.loop.run_in_executor(None, cls.ytdlp.extract_info, f'ytsearch10:{keyword}', False)
        if info is not None:
            embed, id_list = await cls.get_search_result_embed(interaction.user, info)
            message = await interaction.channel.send(embed=embed)
            search_num = len(id_list)
            index_emoji_list = list(cls.index_emoji_dict.keys())
            
            for i in range(search_num):
                await message.add_reaction(index_emoji_list[i])

            def reaction_check(reaction: discord.Reaction, user: discord.Member | discord.User):
                if (reaction.message == message and user == interaction.user and str(reaction.emoji) in index_emoji_list):
                    return True
                return False
            
            try:
                result: tuple[discord.Reaction, discord.Member | discord.User] = await Music.bot.wait_for('reaction_add', check=reaction_check, timeout=10.0)
                reaction = str(result[0].emoji)
                if reaction in cls.index_emoji_dict:
                    await cls.load_yt_song_info(interaction, id_list[cls.index_emoji_dict[reaction]])
                    await message.delete()
                else:
                    print('load_yt_search_info: not reaction in self.index_emoji')
            except asyncio.TimeoutError:
                await message.delete()
        else:
            print('load_yt_search_info: info is None')

    @classmethod
    async def get_search_result_embed(self, user: discord.Member | discord.User, info: dict[str, Any]):
        search_result = []
        id_list: list[str] = []
        if 'entries' in info:
            board = discord.Embed(
                color=discord.Color.blurple(),
                title=f'"{info.get('id')}" 검색 결과',
            )
            board.set_thumbnail(url=user.display_avatar.url)
            board.set_footer(text=user.name, icon_url=user.display_avatar.url)
            for i, song in enumerate(info['entries']):
                if 'title' in song and 'url' in song and song['duration'] is not None:
                    search_result.append(f'{i}. [{song['title']}]({song['url']}) [{self.convert_seconds(song['duration'])}]')
                    id_list.append(song['id'])
                elif song['duration'] is None:
                    info = await Music.bot.loop.run_in_executor(None, self.ytdlp.extract_info, song['url'], False)
                    search_result.append(f'{i}. [{info['title']}]({info['webpage_url']}) [{self.convert_seconds(info['duration'])}]')
                    id_list.append(song['id'])
                else:
                    print('get_search_result_embed: not "title" in song or not "url" in song')
            board.description = '\n'.join(search_result)
            return board, id_list
        else:
            print('get_search_result_embed: not "entries" in info')

    @staticmethod
    def convert_seconds(seconds):
        minutes, seconds = divmod(int(seconds), 60)
        if minutes < 60:
            return f'{minutes:02d}:{seconds:02d}'
        else:
            hours, minutes = divmod(minutes, 60)
            return f'{hours}:{minutes:02d}:{seconds:02d}'


class Music(commands.GroupCog, name='노래'):
    music_player: MusicPlayer = None
    loop: asyncio.AbstractEventLoop
    bot: commands.Bot
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        Music.bot = bot
        Music.loop = bot.loop

    @app_commands.command(name='들려줘')
    async def player(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        ctx = await commands.Context.from_interaction(interaction)
        Music.music_player = await MusicPlayer.from_message(ctx.message)
        await interaction.delete_original_response()
    
    @app_commands.command(name='저장')
    async def save(self, interaction: discord.Interaction, url: str):
        await interaction.response.send_message('ㄱㄷㄱㄷ')
        data = await self.bot.loop.run_in_executor(None, lambda: self.ytdlp.extract_info(url, False))
        print(type(data))
        data_str = json.dumps(data, ensure_ascii=False, indent=4)
        with open(f'./hihi.txt', 'w', encoding='utf-8') as f:
            f.write(data_str)

    @app_commands.command(name='상태')
    async def state(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ctx = await commands.Context.from_interaction(interaction)
        vc = interaction.guild.voice_client
        g = interaction.guild
        count = 0
        '''while True:
            count += 1
            print(count, vc, g.voice_client, interaction.guild.voice_client)
            await asyncio.sleep(0.1)'''
        print(f'self.bot.voice_clients: {self.bot.voice_clients}')
        print(f'type(voice_client): {type(ctx.voice_client)}')
        print(f'interaction.user.voice: {ctx.author.voice}')
        print(f'voice_client.channel: {ctx.voice_client.channel}')
        print(f'voice_client.is_connected: {ctx.voice_client.is_connected()}')
        print(f'voice_client.is_paused: {ctx.voice_client.is_paused()}')
        print(f'voice_client.is_playing: {ctx.voice_client.is_playing()}')
        print(f'playlist.count: {MusicPlayer.playlist.count()}')

    @app_commands.command(name='들어와', description='채널에 들어가요')
    async def join(self, interaction: discord.Interaction):
        await interaction.user.voice.channel.connect(timeout=1)
        await interaction.response.send_message('채널에 들어왔어요')

    @app_commands.command(name='나가라', description='채널에서 나가요')
    async def disconnect(self, interaction: discord.Interaction):
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message('채널에서 나왔어요')

    @app_commands.command(name='볼륨', description='볼륨을 조절해요')
    @app_commands.rename(volume='볼륨')
    @app_commands.describe(volume='기본값은 10% 에요')
    async def volume(self, interaction: discord.Interaction, volume: int):
        self.volume = volume / 100
        source: discord.PCMVolumeTransformer = Music.voice_client.source
        source.volume = volume / 100
        await interaction.response.send_message(f'볼륨은 {int(self.volume * 100)}% 에요')


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))