import aiohttp

import discord
from discord import app_commands
from discord.ext import commands

from ..config import url


@app_commands.guild_only()
class NLP(commands.GroupCog, name='자연어처리'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.label_dict = {0: 'None', 1: '봇이랑 가위바위보를 해요', 2: '주사위를 던져요', 3: '노래 관련 기능을 사용해요', 4: '경고를 줄 멤버를 선택해요'}

    @commands.GroupCog.listener()
    async def on_message(self, message: discord.Message):
        if self.bot.data[message.guild.id]['NLP']:
            if not message.author.bot:
                label = await self.get_label(message.content)
                if label != 0:
                    await message.reply(self.label_dict[label])
    
    async def get_label(self, message_content: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url + message_content) as response:
                return int(response)

    @app_commands.command(name='켜기', description='자연어 처리 기능을 켜요')
    async def turn_on(self, interaction: discord.Interaction):
        self.bot.data[interaction.guild_id]['NLP'] = True
        await interaction.response.send_message('자연어 처리 기능을 켰어요')

    @app_commands.command(name='끄기', description='자연어 처리 기능을 꺼요')
    async def turn_off(self, interaction: discord.Interaction):
        self.bot.data[interaction.guild_id]['NLP'] = False
        await interaction.response.send_message('자연어 처리 기능을 껐어요')


async def setup(bot: commands.Bot):
    await bot.add_cog(NLP(bot))