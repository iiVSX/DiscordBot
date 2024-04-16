import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands


class RPSEmbed(discord.Embed):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(
            color=discord.Color.blurple(),
            title='가위바위보 ✌️✊🤚',
            description='5초 안에 가위, 바위, 보 중 하나를 내야 해요'
        )
        self.set_thumbnail(url=interaction.user.display_avatar.url)
        self.set_footer(text=interaction.user.name, icon_url=interaction.user.display_avatar.url)
        self.interaction = interaction
        self.rps_choice: discord.Reaction = None

    def set_rps_result(self):
        rps_dict = {'✌️': 0, '✊': 1, '🤚': 2}
        rps_rand = random.choice(list(rps_dict.keys()))
        rps_choice_val = rps_dict[str(self.rps_choice.emoji)]
        rps_rand_val = rps_dict[rps_rand]
        result = (rps_choice_val - rps_rand_val) % 3

        result_dict = {0: '🤔 비겼어요', 1: '🤣 이겼어요!', 2: '😵‍💫 졌어요..'}
        self.description = result_dict[result]

        self.add_field(
            name=f'{self.interaction.user.display_name}({self.interaction.user.name}) {str(self.rps_choice.emoji)} vs {rps_rand} {self.rps_choice.message.author.display_name}({self.rps_choice.message.author.name})',
            value=''
        )

    def set_rps_timeout(self):
        self.description = '5초가 지나버렸어요'
        

class RPS:
    def __init__(self):
        self.interaction: discord.Interaction = None
        self.embed: RPSEmbed = None
        self.message: discord.InteractionMessage = None
        self.rps_list = ['✌️', '✊', '🤚']

    async def async_init(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.embed = RPSEmbed(interaction)
        
        await interaction.response.send_message(embed=self.embed)
        self.message = await interaction.original_response()

        for emoji in self.rps_list:
            await self.message.add_reaction(emoji)

    def reaction_check(self, reaction: discord.Reaction, user: discord.Member | discord.User):
        if (reaction.message.id == self.message.id and user == self.interaction.user and str(reaction.emoji) in self.rps_list):
            self.embed.rps_choice = reaction
            return True
        return False

    async def edit_message(self):
        await self.message.edit(embed=self.embed)
        await self.message.clear_reactions()

    async def update_rps_result(self):
        self.embed.set_rps_result()
        await self.edit_message()

    async def handle_timeout(self):
        self.embed.set_rps_timeout()
        await self.edit_message()


class DiceEmbed(discord.Embed):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(
            color=discord.Color.blurple(),
            title='주사위 던지기 🎲',
            description='5초 안에 주사위를 던져야 해요'
        )
        self.set_thumbnail(url=interaction.user.display_avatar.url)

    def set_callback(self):
        self.description = f'결과는 {random.randrange(1, 7)} !!'

    def set_on_timeout(self):
        self.description = '5초가 지나버렸어요'
   

class DiceButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(
            style=discord.ButtonStyle.green,
            label='던져요!',
            emoji='🎲'
        )
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user_id
    
    async def callback(self, interaction: discord.Interaction):    
        view: Dice = self.view
        view.stop()
        view.embed.set_callback()

        self.style = discord.ButtonStyle.red
        self.label = '던졌어요!'
        self.disabled = True

        await interaction.response.edit_message(embed=view.embed, view=view)

    def set_on_timeout(self):
        self.style = discord.ButtonStyle.gray
        self.label = '못던져요..'
        self.disabled = True


class Dice(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=5.0)
        self.embed = None
        self.message = None

    async def async_init(self, interaction: discord.Interaction):
        self.embed = DiceEmbed(interaction)
        self.add_item(DiceButton(interaction.user.id))

        await interaction.response.send_message(embed=self.embed, view=self)
        self.message = await interaction.original_response()

    async def on_timeout(self):
        self.embed.set_on_timeout()
        button: DiceButton = self.children[0]
        button.set_on_timeout()

        await self.message.edit(embed=self.embed, view=self)


class Game(commands.GroupCog, name='게임'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='가위바위보', description='봇이랑 가위바위보를 해요')
    async def play_rps(self, interaction: discord.Interaction):
        rps = RPS()
        await rps.async_init(interaction)

        try:
            await self.bot.wait_for('reaction_add', check=rps.reaction_check, timeout=5.0)
            await rps.update_rps_result()
        except asyncio.TimeoutError:
            await rps.handle_timeout()
    
    @app_commands.command(name='주사위', description='주사위를 던져요')
    async def play_dice(self, interaction: discord.Interaction):
        dice = Dice()
        await dice.async_init(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(Game(bot))