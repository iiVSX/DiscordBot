import asyncio
from urllib import parse

import discord
from discord import app_commands
from discord.ext import commands

import yt_dlp


class MusicPlayer(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.bot: commands.Bot = None
        self.author: discord.Member = None
        self.data: dict[str, bool | int | float | list[dict[str, str]] | dict[discord.Member, int] | dict[str, discord.Message]] = None
        self.history: dict[str, dict[str, str]] = None
        self.guild: discord.Guild = None
        self.channel: discord.TextChannel = None
        self.batch_size = 10
        self.repeat_dict = {0: '➡️', 1: '🔁', 2: '🔂'}
        self.index_dict = {'1️⃣': 0, '2️⃣': 1, '3️⃣': 2, '4️⃣': 3, '5️⃣': 4, '6️⃣': 5, '7️⃣': 6, '8️⃣': 7, '9️⃣': 8, '🔟': 9}
        self.ytdlp = yt_dlp.YoutubeDL({
            'format': 'bestaudio/best',
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            'extract_flat': True,
            'skip_download': True,
        })

        play_btn = discord.ui.Button(row=0)
        play_btn.callback = self.play_btn_callback
        self.add_item(play_btn)

        skip_btn = discord.ui.Button(emoji='⏭️', row=0)
        skip_btn.callback = self.skip_btn_callback
        self.add_item(skip_btn)

        repeat_btn = discord.ui.Button(row=0)
        repeat_btn.callback = self.repeat_btn_callback
        self.add_item(repeat_btn)

        search_btn = discord.ui.Button(emoji='🔍', row=0)
        search_btn.callback = self.search_btn_callback
        self.add_item(search_btn)

        volume_btn = discord.ui.Button(row=0)
        volume_btn.callback = self.volume_btn_callback
        self.add_item(volume_btn)

    @classmethod
    async def from_message(cls, message: discord.Message, bot: commands.Bot):
        music_player = cls()
        music_player.bot = bot
        trigger_msg = await message.channel.fetch_message(message.reference.message_id)
        music_player.author = trigger_msg.author
        music_player.data = bot.data[message.guild.id]
        music_player.history = bot.history
        music_player.guild = message.guild
        music_player.channel = message.channel
        music_player.delete_sent_msg()
        music_player.data['sent_msg']['MusicPlayer'] = await message.edit(content=None, embed=music_player.get_embed(), view=music_player.get_view())
    
    @classmethod
    async def from_sent_msg(cls, message: discord.Message, bot: commands.Bot):
        music_player = cls()
        music_player.bot = bot
        music_player.author = message.author
        music_player.data = bot.data[message.guild.id]
        music_player.history = bot.history
        music_player.guild = message.guild
        music_player.channel = message.channel
        asyncio.run_coroutine_threadsafe(message.edit(embed=music_player.get_embed(), view=music_player.get_view()), bot.loop)

    @classmethod
    async def from_interaction(cls, interaction: discord.Interaction, bot: commands.Bot):
        music_player = cls()
        music_player.bot = bot
        music_player.author = interaction.user
        music_player.data = bot.data[interaction.guild_id]
        music_player.history = bot.history
        music_player.guild = interaction.guild
        music_player.channel = interaction.channel
        music_player.delete_sent_msg()
        music_player.data['sent_msg']['MusicPlayer'] = await interaction.edit_original_response(embed=music_player.get_embed(), view=music_player.get_view())

    def delete_sent_msg(self):
        if 'MusicPlayer' in self.data['sent_msg']:
            asyncio.run_coroutine_threadsafe(self.data['sent_msg']['MusicPlayer'].delete(), self.bot.loop)
            del self.data['sent_msg']['MusicPlayer']
    
    def get_embed(self):
        embed = discord.Embed(color=discord.Color.blurple())
        embed.add_field(name='', value='', inline=False)
        embed.set_footer(text=self.author, icon_url=self.author.display_avatar.url)

        if self.guild.voice_client is not None and self.guild.voice_client.is_connected():
            if self.guild.voice_client.is_playing():
                embed.title = '▶️  재생 중'
            elif self.guild.voice_client.is_paused():
                embed.title = '⏸️  일시 정지'
            else:
                embed.title = '⏹️  대기 중'
        else:
            embed.title = '⏹️  대기 중'
        embed.title += f'  -  음량 {int(self.data['volume'] * 400)}%'

        playlist = self.data['playlist']
        if playlist:
            embed.description = f'[{playlist[0]['title']}]({playlist[0]['url']}) [{(playlist[0]['length'])}]\n\n{playlist[0]['artist'] if 'artist' in playlist[0] else ''}'
            embed.set_thumbnail(url=playlist[0]['thumbnail'])

            for i in range(0, len(playlist), self.batch_size):
                embed.add_field(
                    name='[Playlist]' if i == 0 else '',
                    value='\n'.join([f'{i + j + 1}. [{song['title']}]({song['url']}) [{song['length']}]' for j, song in enumerate(playlist[i:min(i + self.batch_size, len(playlist))])]),
                    inline=False,
                )
        else:
            embed.description = '재생할 수 있는 노래가 없어요 :(\n\n플레이리스트에 노래를 넣어야 해요'
            embed.set_thumbnail(url=self.author.display_avatar.url)
            embed.add_field(name='[Playlist]', value='비어있어요...', inline=False)

        return embed
    
    def get_view(self):
        play_btn = self.children[0]
        if self.guild.voice_client is not None and self.guild.voice_client.is_connected() and self.guild.voice_client.is_playing():
            play_btn.emoji = '⏸️'
        else:
            play_btn.emoji = '▶️'

        repeat_btn = self.children[2]
        repeat_btn.emoji = self.repeat_dict[self.data['repeat']]

        volume = self.data['volume']
        volume_btn = self.children[4]
        if volume > 0.5:
            print('[get_view] volume > 0.5')
        elif volume > 0.25:
            volume_btn.emoji = '🔊'
        elif volume > 0:
            volume_btn.emoji = '🔉'
        elif volume == 0:
            volume_btn.emoji = '🔇'
        else:
            print('[get_view] volume < 0')

        return self
    
    async def interaction_check(self, interaction: discord.Interaction):
        guild = interaction.guild
        if interaction.user.voice is not None:
            if guild.voice_client is None or not guild.voice_client.is_connected():
                await interaction.user.voice.channel.connect(timeout=2)
                return True
            if interaction.user.voice.channel == guild.voice_client.channel:
                return True
            if not guild.voice_client.is_playing():
                await guild.voice_client.move_to(interaction.user.voice.channel, timeout=2)
                return True
            else:
                await interaction.response.send_message(f'{interaction.user.mention} 다른 채널에서 사용하고 있어요...')
        else:
            await interaction.response.send_message(f'{interaction.user.mention} 음성 채널에 참여해야 사용할 수 있어요...')
        return False
        
    async def search_modal_interaction_check(self, interaction: discord.Interaction):
        keyword = interaction.data['components'][0]['components'][0]['value']
        url = interaction.data['components'][1]['components'][0]['value']
        return keyword or url
    
    async def volume_modal_interaction_check(self, interaction: discord.Interaction):
        try:
            volume = int(interaction.data['components'][0]['components'][0]['value'])
            return 0 <= volume <= 200
        except Exception:
            return False
        
    async def play_btn_callback(self, interaction: discord.Interaction):
        asyncio.run_coroutine_threadsafe(interaction.response.defer(), self.bot.loop)
        self.author = interaction.user

        guild = interaction.guild
        if guild.voice_client.is_playing():
            guild.voice_client.pause()
        elif guild.voice_client.is_paused():
            guild.voice_client.resume()
        else:
            self.play_song()
            return
        
        await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())

    def play_song(self):
        playlist = self.data['playlist']
        if playlist:
            self.guild.voice_client.play(
                discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(
                        playlist[0]['source'],
                        before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                        options='-vn',
                    ),
                    self.data['volume'],
                ),
                after=self.play_after,
                bitrate=512,
                expected_packet_loss=0.01,
                signal_type='music',
            )
        else:
            print('[play_song] playlist is empty')
            
        asyncio.run_coroutine_threadsafe(self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view()), self.bot.loop)

    def play_after(self, error: Exception = None):
        if self.guild.voice_client is not None and self.guild.voice_client.is_connected():
            playlist = self.data['playlist']
            repeat = self.data['repeat']
            if error:
                print(f'[play_after] {error}')
            if playlist:
                if repeat == 0:
                    del playlist[0]
                elif repeat == 1 or repeat == 2:
                    playlist.append(playlist.pop(0))
                else:
                    print('[play_after] repeat != (0 or 1 or 2)')
                    
                self.play_song()
            else:
                asyncio.run_coroutine_threadsafe(self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view()), self.bot.loop)

    async def skip_btn_callback(self, interaction: discord.Interaction):
        asyncio.run_coroutine_threadsafe(interaction.response.defer(), self.bot.loop)
        self.author = interaction.user
        
        guild = interaction.guild
        if guild.voice_client.is_playing() or guild.voice_client.is_paused():
            guild.voice_client.stop()
        else:
            self.play_after()

    async def repeat_btn_callback(self, interaction: discord.Interaction):
        asyncio.run_coroutine_threadsafe(interaction.response.defer(), self.bot.loop)
        self.author = interaction.user
        
        self.data['repeat'] = (self.data['repeat'] + 1) % 3
        
        await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())

    async def search_btn_callback(self, interaction: discord.Interaction):     
        search_modal = discord.ui.Modal(title='노래 가져오기 🎹')
        search_modal.add_item(discord.ui.TextInput(label='검색어', placeholder='검색어를 입력해요', required=False, row=0))
        search_modal.add_item(discord.ui.TextInput(label='URL', placeholder='URL을 입력해요', required=False, row=1))
        search_modal.interaction_check = self.search_modal_interaction_check
        search_modal.on_submit = self.search_modal_on_submit
        asyncio.run_coroutine_threadsafe(interaction.response.send_modal(search_modal), self.bot.loop)

        await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())

    async def volume_btn_callback(self, interaction: discord.Interaction):     
        volume_modal = discord.ui.Modal(title='음량 조절하기 🔈')
        volume_modal.add_item(discord.ui.TextInput(label='음량', placeholder='0에서 200 사이의 정수를 입력해요', required=True, row=0))
        volume_modal.interaction_check = self.volume_modal_interaction_check
        volume_modal.on_submit = self.volume_modal_on_submit
        asyncio.run_coroutine_threadsafe(interaction.response.send_modal(volume_modal), self.bot.loop)

        await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())

    async def search_modal_on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        keyword = interaction.data['components'][0]['components'][0]['value']
        url = interaction.data['components'][1]['components'][0]['value']
        author = interaction.user
        if keyword:
            await self.pick_yt_search10(keyword, author)
        if url:
            is_list, id = self.url_to_id(url)
            if id is not None:
                if is_list:
                    await self.append_yt_playlist(id, author)
                else:
                    await self.append_yt_song(id, author)
            else:

                await self.data['sent_msg']['MusicPlayer'].reply(f'{interaction.user.mention} 지원하지 않는 URL이에요...')

    async def pick_yt_search10(self, keyword: str, author: discord.Member):
        search_list = await self.load_yt_search10(keyword)
        message = await self.data['sent_msg']['MusicPlayer'].reply(embed=self.get_yt_search10_embed(keyword, search_list, author))

        index_emoji_list = list(self.index_dict.keys())
        for i in range(len(search_list)):
            asyncio.run_coroutine_threadsafe(message.add_reaction(index_emoji_list[i]), self.bot.loop)

        def reaction_check(reaction: discord.Reaction, user: discord.Member):
            return user == author and reaction.message == message and reaction.emoji in self.index_dict
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=reaction_check, timeout=15)
            reaction = reaction.emoji
            id = search_list[self.index_dict[reaction]]['id']
            
            await self.append_yt_song(id, author)
            asyncio.run_coroutine_threadsafe(message.delete(), self.bot.loop)
        except asyncio.TimeoutError:
            asyncio.run_coroutine_threadsafe(message.delete(), self.bot.loop)

    async def load_yt_search10(self, keyword: str):
        search_list = []
        async with self.channel.typing():
            info = await self.bot.loop.run_in_executor(None, self.ytdlp.extract_info, f'ytsearch10:{keyword}', False)
        if info is not None:
            if 'entries' in info:
                for song in info['entries']:
                    if all(key in song for key in ['id', 'title', 'url']):
                        search = {
                            'id': song['id'],
                            'title': song['title'],
                            'url': song['url'],
                        }
                        search_list.append(search)
                    else:
                        print(f'[load_yt_search10] not all(key in song for key in ["id", "title", "url"])')
            else:
                print('[load_yt_search10] "entries" not in info')
        else:
            print('[load_yt_search10] info is None')
        
        return search_list

    def get_yt_search10_embed(self, keyword: str, list: list[dict[str, str]], author: discord.Member):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title=f'🖥️  "{keyword}" 검색 결과',
            description='\n'.join([f'{i + 1}. [{search['title']}]({search['url']})' for i, search in enumerate(list)]),
        )
        embed.set_thumbnail(url=author.display_avatar.url)
        embed.set_footer(text=author, icon_url=author.display_avatar.url)

        return embed
    
    async def append_yt_song(self, id: str, author: discord.Member):
        playlist = self.data['playlist']
        if id in self.history:
            song = self.history[id]
            playlist.append(song)
            self.author = author
            await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())
            return
        song = await self.load_yt_song(id)
        if song is not None:
            self.history[song['id']] = song
            playlist.append(song)
            self.author = author
            await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())

    async def load_yt_song(self, id: str):
        async with self.channel.typing():
            info = await self.bot.loop.run_in_executor(None, self.ytdlp.extract_info, 'https://music.youtube.com/watch?v=' + id, False)
        if info is not None:
            if all(key in info for key in ['duration', 'id', 'thumbnail', 'thumbnails', 'title', 'url', 'webpage_url']):
                song = {
                    'id': info['id'],
                    'length': self.seconds_to_time(info['duration']),
                    'source': info['url'],
                    'title': info['title'],
                    'url': info['webpage_url'],
                }

                square_thumbnail = self.get_square_thumbnail(info['thumbnails'])
                if square_thumbnail is not None:
                    song['thumbnail'] = square_thumbnail
                else:
                    song['thumbnail'] = info['thumbnail']

                if 'artist' in info:
                    song['artist'] = info['artist']

                return song
            else:
                print('[get_song] not all(key in info for key in ["id", "duration", "url", "thumbnail", "thumbnails", "title", "webpage_url"])')
        else:
            print('[get_song] info is None')
            
        return
    
    @staticmethod
    def seconds_to_time(seconds: int):
        minutes, seconds = divmod(int(seconds), 60)
        if minutes < 60:
            return f'{minutes:02d}:{seconds:02d}'
        else:
            hours, minutes = divmod(minutes, 60)
            return f'{hours}:{minutes:02d}:{seconds:02d}'

    @staticmethod
    def get_square_thumbnail(thumbnails: list[dict[str, int | str]]):
        max_res_square = 0
        max_res_square_thumbnail = None

        for thumbnail in thumbnails:
            if all(key in thumbnail for key in ['height', 'width', 'url']):
                url = thumbnail['url']
                height = thumbnail['height']
                width = thumbnail['width']
                if height == width and height > max_res_square:
                    max_res_square = height
                    max_res_square_thumbnail = url

        return max_res_square_thumbnail
    
    @staticmethod
    def url_to_id(url: str):
        parsed_url = parse.urlparse(url)
        query_dict = parse.parse_qs(parsed_url.query)
        if 'list' in query_dict:
            return (True, query_dict['list'][0])
        elif 'v' in query_dict:
            return (False, query_dict['v'][0])
        elif parsed_url.netloc == 'youtu.be':
            return (False, parsed_url.path[1:])
        elif parsed_url.path.startswith('/shorts/'):
            return (False, parsed_url.path[8:])
        elif parsed_url.path.startswith('/live/'):
            return (False, parsed_url.path[6:])
        else:
            return (None, None)
        
    async def append_yt_playlist(self, id: str, author: discord.Member):
        song_id_list = await self.load_yt_playlist(id)
        for song_id in song_id_list:
            await self.append_yt_song(song_id, author)

    async def load_yt_playlist(self, id: str):
        song_id_list = []
        async with self.channel.typing():
            info = await self.bot.loop.run_in_executor(None, self.ytdlp.extract_info, 'https://music.youtube.com/playlist?list=' + id, False)
        if info is not None:
            if 'entries' in info:
                for song in info['entries']:
                    if 'id' in song:
                        song_id_list.append(song['id'])
                    else:
                        print(f'[load_yt_playlist] "id" not in song')
            else:
                print('[load_yt_playlist] "entries" not in info')
        else:
            print('[load_yt_playlist] info is None')
        
        return song_id_list

    async def volume_modal_on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.author = interaction.user

        volume = int(interaction.data['components'][0]['components'][0]['value']) / 400
        self.data['volume'] = volume

        guild = interaction.guild
        if guild.voice_client is not None and guild.voice_client.is_connected():
            if guild.voice_client.is_playing() or guild.voice_client.is_paused():
                guild.voice_client.source.volume = volume
        
        await self.data['sent_msg']['MusicPlayer'].edit(embed=self.get_embed(), view=self.get_view())


@app_commands.guild_only()
class Music(commands.GroupCog, name='노래'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.GroupCog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user and message.content == '노래 관련 기능을 사용해요':
            await MusicPlayer.from_message(message, self.bot)

    @commands.GroupCog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member == self.bot.user and before.channel is not None and after.channel is None:
            await MusicPlayer.from_sent_msg(self.bot.data[member.guild.id]['sent_msg']['MusicPlayer'], self.bot)

    @app_commands.command(name='리모컨', description='노래 관련 기능을 사용해요')
    async def remote_control(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await MusicPlayer.from_interaction(interaction, self.bot)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))