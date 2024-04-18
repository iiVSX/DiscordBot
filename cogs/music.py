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
        await interaction.response.edit_message(embed=MusicPlayer.get_embed(interaction.user, interaction.guild), view=self.view)


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
    def __init__(self, guild: discord.Guild):
        super().__init__(row=0)
        self.set_emoji(guild)

    def set_emoji(self, guild: discord.Guild):
        self.emoji = MusicPlayer.repeat_dict.get(MusicPlayer.data[guild.id]['repeat'])

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        MusicPlayer.data[interaction.guild.id]['repeat'] = (MusicPlayer.data[interaction.guild.id]['repeat'] + 1) % 3

        self.set_emoji(interaction.guild)
        await interaction.response.edit_message(embed=MusicPlayer.get_embed(interaction.user, interaction.guild), view=self.view)


class VolumeButton(discord.ui.Button):
    def __init__(self, guild: discord.Guild):
        super().__init__(row=0)
        self.set_emoji(guild)

    def set_emoji(self, guild: discord.Guild):
        volume = MusicPlayer.data[guild.id]['volume']
        if volume < 0:
            print('[VolumeButton:set_emoji] volume < 0')
        else:
            if volume == 0:
                self.emoji = '🔇'
            elif volume <= 0.25:
                self.emoji = '🔉'
            elif volume <= 0.5:
                self.emoji = '🔊'
            else:
                print('[VolumeButton:set_emoji] volume > 0.5')

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VolumeModal(self))


class VolumeModal(discord.ui.Modal):
    def __init__(self, volume_button: VolumeButton):
        super().__init__(title='음량 조절하기 🔈')
        self.vb = volume_button
        volume = discord.ui.TextInput(
            label='음량',
            placeholder='0에서 200 사이의 정수를 입력해요',
            required=True,
            row=0
        )
        self.add_item(volume)

    async def interaction_check(self, interaction: discord.Interaction):
        try:
            volume = int(self.children[0].value)
            return 0 <= volume <= 200
        except Exception:
            return False

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        volume = int(self.children[0].value) / 400
        MusicPlayer.data[interaction.guild.id]['volume'] = volume
        if interaction.guild.voice_client is not None and interaction.guild.voice_client.is_connected():
            if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused():
                interaction.guild.voice_client.source.volume = volume
        self.vb.set_emoji(interaction.guild)
        await interaction.edit_original_response(embed=MusicPlayer.get_embed(interaction.user, interaction.guild), view=self.vb.view)


class SearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji='🔍', row=0)

    async def interaction_check(self, interaction: discord.Interaction):
        return await self.view.interaction_check(interaction)
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal())
        await interaction.edit_original_response(embed=MusicPlayer.get_embed(interaction.user, interaction.guild))


class SearchModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title='노래 가져오기 🎹')
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
        self.add_item(keyword)
        self.add_item(url)

    async def interaction_check(self, interaction: discord.Interaction):
        return len(self.children[0].value) or len(self.children[1].value)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        if len(self.children[0].value):
            await MusicPlayer.load_yt_search_info(interaction, self.children[0].value)
        if len(self.children[1].value):
            query_str_dict = parse.parse_qs(parse.urlparse(self.children[1].value).query)
            if 'list' in query_str_dict:
                await MusicPlayer.load_yt_playlist_info(interaction, query_str_dict.get('list')[0])
            elif 'v' in query_str_dict:
                await MusicPlayer.load_yt_song_info(interaction, query_str_dict.get('v')[0])
            else:
                print('SearchModal:on_submit: invalid youtube url')


class MusicPlayer(discord.ui.View):
    history: dict[str, dict[str, str | int]] = {}
    playlist: list[dict[str, str | int]] = []
    sended_msg: discord.Message = None
    volume = 0.1
    repeat = 0
    repeat_dict = {0: '➡️', 1: '🔁', 2: '🔂'}
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
    data: dict[int, dict[str, int | float | list[dict[str, str | int]] | discord.Message]] = {}
    embed_batch_size = 10
    index_emoji_dict = {'1️⃣': 0, '2️⃣': 1, '3️⃣': 2, '4️⃣': 3, '5️⃣': 4, '6️⃣': 5, '7️⃣': 6, '8️⃣': 7, '9️⃣': 8, '🔟': 9}
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    def get_embed(cls, user: discord.User | discord.Member, guild: discord.Guild):
        embed = discord.Embed(color=discord.Color.blurple())
        playlist = cls.data[guild.id]['playlist']

        if guild.voice_client is not None and guild.voice_client.is_connected():
            if guild.voice_client.is_playing():
                embed.title = '▶️  재생 중'
            elif guild.voice_client.is_paused():
                embed.title = '⏸️  일시 정지'
            else:
                embed.title = '⏹️  대기 중'
        else:
            embed.title = '⏹️  대기 중'

        embed.title += f'  -  음량 {int(cls.data[guild.id]['volume'] * 400)}%'
        embed.add_field(name='', value='', inline=False)

        if playlist:
            embed.description = f'[{playlist[0]['title']}]({playlist[0]['url']}) [{cls.convert_seconds(playlist[0]['length'])}]\n\n{playlist[0].get('artist') if 'artist' in playlist[0] else ''}'
            embed.set_thumbnail(url=playlist[0]['thumbnail'])

            for i in range(0, len(playlist), cls.embed_batch_size):
                embed.add_field(
                    name='[Playlist]' if i == 0 else '',
                    value='\n'.join([f'{i + j + 1}. [{song.get("title")}]({song.get("url")}) [{cls.convert_seconds(song.get("length"))}]' for j, song in enumerate(playlist[i:min(i + cls.embed_batch_size, len(playlist))])]),
                    inline=False
                )
        else:
            embed.description = '재생할 수 있는 노래가 없어요 :(\n\n플레이리스트에 노래를 넣어야 해요'
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name='[Playlist]', value='비어있어요...', inline=False)

        embed.set_footer(text=user, icon_url=user.display_avatar.url)

        return embed

    @classmethod
    async def from_message(cls, message: discord.Message):
        music_player = cls()
        if cls.data.get(message.guild.id) is None:
            cls.data[message.guild.id] = {
                'playlist': [],
                'volume': 0.1,
                'repeat': 0,
            }
        else:
            asyncio.run_coroutine_threadsafe(cls.data[message.guild.id]['message'].delete(), Music.bot.loop)

        play_button = PlayButton(message.guild)
        skip_button = SkipButton()
        repeat_button = RepeatButton(message.guild)
        search_button = SearchButton()
        volume_button = VolumeButton(message.guild)
        music_player.add_item(play_button)
        music_player.add_item(skip_button)
        music_player.add_item(repeat_button)
        music_player.add_item(search_button)
        music_player.add_item(volume_button)
        cls.data[message.guild.id]['message'] = await message.channel.send(embed=cls.get_embed(message.author, message.guild), view=music_player)
        return music_player

    def play_song(self, interaction: discord.Interaction):
        playlist = MusicPlayer.data[interaction.guild.id]['playlist']
        if playlist:
            interaction.guild.voice_client.play(
                source=discord.PCMVolumeTransformer(
                    original=discord.FFmpegPCMAudio(
                        source=playlist[0]['source'],
                        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                        options='-vn',
                    ),
                    volume=MusicPlayer.data[interaction.guild.id]['volume'],
                ),
                after=lambda e: self.play_after(e, interaction),
                bitrate=512,
                expected_packet_loss=0.01,
                signal_type='music',
            )
        else:
            print('play_song: playlist is empty')

        self.children[0].set_emoji(interaction.guild)
        asyncio.run_coroutine_threadsafe(interaction.edit_original_response(embed=MusicPlayer.get_embed(interaction.user, interaction.guild), view=self), Music.bot.loop)

    def play_after(self, error: Exception | None, interaction: discord.Interaction):
        playlist = MusicPlayer.data[interaction.guild.id]['playlist']
        repeat = MusicPlayer.data[interaction.guild.id]['repeat']
        if error:
            print(f'play_after: {error}')
        if playlist:
            if repeat == 0:
                del playlist[0]
            elif repeat == 1 or repeat == 2:
                playlist.append(playlist.pop(0))
            else:
                print('[play_after] not cls.repeat == 0 and not cls.repeat == 1 and not cls.repeat == 2')
                
            self.play_song(interaction)
        else:
            self.children[0].set_emoji(interaction.guild)
            asyncio.run_coroutine_threadsafe(interaction.edit_original_response(embed=MusicPlayer.get_embed(interaction.user, interaction.guild), view=self), Music.bot.loop)
            print('play_after: cls.playlist is empty')

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
        playlist = MusicPlayer.data[interaction.guild.id]['playlist']
        song = cls.history.get(id)
        if song is not None:
                playlist.append(song)
                await MusicPlayer.data[interaction.guild.id]['message'].edit(embed=cls.get_embed(interaction.user, interaction.guild))
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
                cls.history[song['id']] = song
                playlist.append(song)
                await MusicPlayer.data[interaction.guild.id]['message'].edit(embed=cls.get_embed(interaction.user, interaction.guild))
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


@app_commands.guild_only()
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
        await interaction.response.defer(thinking=True)
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
        print(f'voice_client.source.volume: {ctx.voice_client.source.volume}')
        print(f'voice_client.channel: {ctx.voice_client.channel}')
        print(f'voice_client.is_connected: {ctx.voice_client.is_connected()}')
        print(f'voice_client.is_paused: {ctx.voice_client.is_paused()}')
        print(f'voice_client.is_playing: {ctx.voice_client.is_playing()}')
        print(f'playlist.count: {MusicPlayer.playlist.count()}')
        await interaction.delete_original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))