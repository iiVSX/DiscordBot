import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands
        

class RPS():
    dict = {'✌️': 0, '✊': 1, '🤚': 2}
    result_dict = {0: '🤔 비겼어요', 1: '🤣 이겼어요!', 2: '😵‍💫 졌어요..'}
    def __init__(self, message: discord.Message):
        self.trigger_msg = message
        self.sent_msg: discord.Message = None
        self.state = 0
        self.user_pick: str = None

    @classmethod
    async def from_message(cls, message: discord.Message, bot: commands.Bot):
        rps = cls(message)
        rps.sent_msg = await message.channel.send(embed=rps.get_embed())

        for emoji in RPS.dict.keys():
            await rps.sent_msg.add_reaction(emoji)

        def check(reaction: discord.Reaction, user: discord.Member):
            return reaction.message == rps.sent_msg and user == message.author and reaction.emoji in RPS.dict
        
        try:
            reaction, user = await bot.wait_for('reaction_add', check=check, timeout=5)
            rps.user_pick = reaction.emoji
            await rps.callback()
        except asyncio.TimeoutError:
            await rps.on_timeout()

    def get_embed(self):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title='가위바위보 ✌️✊🤚',
        )
        embed.set_thumbnail(url=self.trigger_msg.author.display_avatar.url)

        if self.state == 0:
            embed.description = '5초 안에 가위, 바위, 보 중 하나를 내야 해요'
        elif self.state == 1:
            rand_pick, rand_pick_val = random.choice(list(RPS.dict.items()))
            user_pick_val = RPS.dict[self.user_pick]
            result = (user_pick_val - rand_pick_val) % 3
            embed.description = RPS.result_dict[result]
            embed.add_field(
                name=f'{self.trigger_msg.author.display_name}({self.trigger_msg.author}) {self.user_pick} vs {rand_pick} {self.sent_msg.author.display_name}({self.sent_msg.author})',
                value=''
            )
        elif self.state == 2:
            embed.description = '5초가 지나버렸어요'
        else:
            print('[RPS][get_embed]: state != (0 or 1 or 2)')

        embed.set_footer(text=self.trigger_msg.author, icon_url=self.trigger_msg.author.display_avatar.url)

        return embed

    async def callback(self):
        self.state = 1
        await self.sent_msg.edit(embed=self.get_embed())
        
    async def on_timeout(self):
        self.state = 2
        await self.sent_msg.edit(embed=self.get_embed())


class Dice(discord.ui.View):
    def __init__(self, message: discord.Message):
        super().__init__(timeout=5)
        self.trigger_msg = message
        self.sent_msg: discord.Message = None
        self.state = 0
        button = discord.ui.Button(
            emoji='🎲',
            row=0,
        )
        button.callback = self.callback
        self.add_item(button)

    @classmethod
    async def from_message(cls, message: discord.Message):
        dice = cls(message)
        dice.sent_msg = await message.channel.send(embed=dice.get_embed(), view=dice.get_view())

        return dice
    
    def get_embed(self):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title='🎲  주사위 던지기',
        )
        embed.set_thumbnail(url=self.trigger_msg.author.display_avatar.url)

        if self.state == 0:
            embed.description = '5초 안에 주사위를 던져야 해요'
        elif self.state == 1:
            embed.description = f'결과는 {random.randrange(1, 7)} !!'
        elif self.state == 2:
            embed.description = '5초가 지나버렸어요'
        else:
            print('[Dice][get_embed]: state != (0 or 1 or 2)')

        embed.set_footer(text=self.trigger_msg.author, icon_url=self.trigger_msg.author.display_avatar.url)

        return embed

    def get_view(self):
        if self.state == 0:
            self.children[0].style = discord.ButtonStyle.green
            self.children[0].label = '던져요!'
        elif self.state == 1:
            self.children[0].style = discord.ButtonStyle.red
            self.children[0].label = '던졌어요!'
            self.children[0].disabled = True
        elif self.state == 2:
            self.children[0].style = discord.ButtonStyle.gray
            self.children[0].label = '못던저요..'
            self.children[0].disabled = True
        else:
            print('[Dice][set_button]: state != (0 or 1 or 2)')

        return self
    
    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.trigger_msg.author
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        self.state = 1
        await self.sent_msg.edit(embed=self.get_embed(), view=self.get_view())

    async def on_timeout(self):
        self.state = 2
        await self.sent_msg.edit(embed=self.get_embed(), view=self.get_view())


@app_commands.guild_only()
class Game(commands.GroupCog, name='게임'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='가위바위보', description='봇이랑 가위바위보를 해요')
    async def play_rps(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await interaction.delete_original_response()
        ctx = await commands.Context.from_interaction(interaction)
        await RPS.from_message(ctx.message, self.bot)
    
    @app_commands.command(name='주사위', description='주사위를 던져요')
    async def play_dice(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await interaction.delete_original_response()
        ctx = await commands.Context.from_interaction(interaction)
        await Dice.from_message(ctx.message)
        

async def setup(bot: commands.Bot):
    await bot.add_cog(Game(bot))