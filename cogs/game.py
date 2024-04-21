import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands
        

class RPS():
    def __init__(self):
        self.bot: commands.Bot = None
        self.author: discord.Member = None
        self.sent_msg: discord.Message = None
        self.state = 0
        self.user_pick: str = None
        self.rps_dict = {'✌️': 0, '✊': 1, '🤚': 2}
        self.result_dict = {0: '🤔 비겼어요', 1: '🤣 이겼어요!', 2: '😵‍💫 졌어요..'}

    @classmethod
    async def from_message(cls, message: discord.Message, bot: commands.Bot):
        rps = cls()
        rps.bot = bot
        trigger_msg = await message.channel.fetch_message(message.reference.message_id)
        rps.author = trigger_msg.author
        rps.sent_msg = await message.edit(content=None, embed=rps.get_embed())
        rps.add_reactions()
        await rps.wait_for_reaction()
    
    @classmethod
    async def from_interaction(cls, interaction: discord.Interaction, bot: commands.Bot):
        rps = cls()
        rps.bot = bot
        rps.author = interaction.user
        rps.sent_msg = await interaction.edit_original_response(embed=rps.get_embed())
        rps.add_reactions()
        await rps.wait_for_reaction()

    def get_embed(self):
        embed = discord.Embed(color=discord.Color.blurple(), title='가위바위보 ✌️✊🤚')
        embed.set_thumbnail(url=self.author.display_avatar.url)
        embed.set_footer(text=self.author, icon_url=self.author.display_avatar.url)

        if self.state == 0:
            embed.description = '5초 안에 가위, 바위, 보 중 하나를 내야 해요'
        elif self.state == 1:
            bot_pick, bot_pick_val = random.choice(list(self.rps_dict.items()))
            user_pick_val = self.rps_dict[self.user_pick]
            result = (user_pick_val - bot_pick_val) % 3
            embed.description = self.result_dict[result]
            embed.add_field(
                name=f'{self.author.display_name}({self.author}) {self.user_pick} vs {bot_pick} {self.sent_msg.author.display_name}({self.sent_msg.author})',
                value='',
                inline=False,
            )
        elif self.state == 2:
            embed.description = '5초가 지나버렸어요'
        else:
            print('[RPS][get_embed]: state != (0 or 1 or 2)')

        return embed
    
    def add_reactions(self):
        for emoji in self.rps_dict.keys():
            asyncio.run_coroutine_threadsafe(self.sent_msg.add_reaction(emoji), self.bot.loop)
    
    async def wait_for_reaction(self):
        try:
            reaction, user = await self.bot.wait_for('reaction_add', check=self.reaction_check, timeout=5) 
            await self.callback(reaction.emoji)
        except asyncio.TimeoutError:
            await self.on_timeout()

    def reaction_check(self, reaction: discord.Reaction, user: discord.Member):
        return user == self.author and reaction.message == self.sent_msg and reaction.emoji in self.rps_dict

    async def callback(self, emoji: discord.Emoji):
        self.state = 1
        self.user_pick = emoji
        await self.sent_msg.edit(embed=self.get_embed())
        
    async def on_timeout(self):
        asyncio.run_coroutine_threadsafe(self.sent_msg.clear_reactions(), self.bot.loop)
        self.state = 2
        await self.sent_msg.edit(embed=self.get_embed())


class Dice(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=5)
        self.bot: commands.Bot = None
        self.author: discord.Member = None
        self.sent_msg: discord.Message = None
        self.state = 0
        button = discord.ui.Button(emoji='🎲', row=0)
        button.callback = self.callback
        self.add_item(button)

    @classmethod
    async def from_message(cls, message: discord.Message, bot: commands.Bot):
        dice = cls()
        dice.bot = bot
        trigger_msg = await message.channel.fetch_message(message.reference.message_id)
        dice.author = trigger_msg.author
        dice.sent_msg = await message.edit(content=None, embed=dice.get_embed(), view=dice.get_view())
    
    @classmethod
    async def from_interaction(cls, interaction: discord.Interaction, bot: commands.Bot):
        dice = cls()
        dice.bot = bot
        dice.author = interaction.user
        dice.sent_msg = await interaction.edit_original_response(embed=dice.get_embed(), view=dice.get_view())
    
    def get_embed(self):
        embed = discord.Embed(color=discord.Color.blurple(), title='🎲  주사위 던지기')
        embed.set_thumbnail(url=self.author.display_avatar.url)
        embed.set_footer(text=self.author, icon_url=self.author.display_avatar.url)

        if self.state == 0:
            embed.description = '5초 안에 주사위를 던져야 해요'
        elif self.state == 1:
            embed.description = f'결과는 {random.randrange(1, 7)} !!'
        elif self.state == 2:
            embed.description = '5초가 지나버렸어요'
        else:
            print('[Dice][get_embed]: state != (0 or 1 or 2)')

        return embed

    def get_view(self):
        button = self.children[0]
        if self.state == 0:
            button.style = discord.ButtonStyle.green
            button.label = '던져요!'
        elif self.state == 1:
            button.style = discord.ButtonStyle.red
            button.label = '던졌어요!'
            button.disabled = True
        elif self.state == 2:
            button.style = discord.ButtonStyle.gray
            button.label = '못던저요..'
            button.disabled = True
        else:
            print('[Dice][get_view]: state != (0 or 1 or 2)')

        return self
    
    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message(f'{interaction.user.mention} 다른 사람 거에요...')
            return False
        return True
    
    async def callback(self, interaction: discord.Interaction):
        asyncio.run_coroutine_threadsafe(interaction.response.defer(), self.bot.loop)
        self.state = 1
        self.stop()
        await self.sent_msg.edit(embed=self.get_embed(), view=self.get_view())
        
    async def on_timeout(self):
        self.state = 2
        await self.sent_msg.edit(embed=self.get_embed(), view=self.get_view())


@app_commands.guild_only()
class Game(commands.GroupCog, name='게임'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.GroupCog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            if message.content == '봇이랑 가위바위보를 해요':
                await RPS.from_message(message, self.bot)
            elif message.content == '주사위를 던져요':
                await Dice.from_message(message, self.bot)

    @app_commands.command(name='가위바위보', description='봇이랑 가위바위보를 해요')
    async def play_rps(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await RPS.from_interaction(interaction, self.bot)
    
    @app_commands.command(name='주사위', description='주사위를 던져요')
    async def play_dice(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await Dice.from_interaction(interaction, self.bot)
        

async def setup(bot: commands.Bot):
    await bot.add_cog(Game(bot))