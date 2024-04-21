import asyncio

import discord
from discord import app_commands
from discord.ext import commands


class Caution(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.bot: commands.Bot = None
        self.author: discord.Member = None
        self.data: dict[str, bool | int | float | list[dict[str, str]] | dict[discord.Member, int] | dict[str, discord.Message]] = None
        user_select = discord.ui.UserSelect(placeholder='경고를 줄 멤버를 선택해요', row=0)
        user_select.callback = self.callback
        self.add_item(user_select)

    @classmethod
    async def from_message(cls, message: discord.Message, bot: commands.Bot):
        caution = cls()
        caution.bot = bot
        trigger_msg = await message.channel.fetch_message(message.reference.message_id)
        caution.author = trigger_msg.author
        caution.data = bot.data[message.guild.id]
        caution.delete_sent_msg()
        caution.data['sent_msg']['Caution'] = await message.edit(content=None, embed=caution.get_embed(), view=caution)
    
    @classmethod
    async def from_interaction(cls, interaction: discord.Interaction, bot: commands.Bot):
        caution = cls()
        caution.bot = bot
        caution.author = interaction.user
        caution.data = bot.data[interaction.guild_id]
        caution.delete_sent_msg()
        caution.data['sent_msg']['Caution'] = await interaction.edit_original_response(embed=caution.get_embed(), view=caution)

    def delete_sent_msg(self):
        if 'Caution' in self.data['sent_msg']:
            asyncio.run_coroutine_threadsafe(self.data['sent_msg']['Caution'].delete(), self.bot.loop)
            del self.data['sent_msg']['Caution']
    
    def get_embed(self):
        embed = discord.Embed(color=discord.Color.blurple(), title='⚠️  경고')
        embed.set_thumbnail(url=self.author.display_avatar.url)
        embed.add_field(name='', value='', inline=False)
        embed.set_footer(text=self.author, icon_url=self.author.display_avatar.url)

        caution_dict = self.data['caution_dict']
        if caution_dict:
            embed.description = '경고를 받은 멤버목록이에요\n\n쫓겨나지 않게 조심해야 해요'
            for member, count in caution_dict.items():
                embed.add_field(
                    name=f'{member.display_name}({member})',
                    value=f'경고 {count}회',
                    inline=False,
                )
        else:
            embed.description = '경고받은 멤버가 없어요\n\n심심한 곳이네요'

        return embed
    
    async def callback(self, interaction: discord.Interaction):
        asyncio.run_coroutine_threadsafe(interaction.response.defer(), self.bot.loop)
        self.author = interaction.user

        member = self.children[0].values[0]
        caution_dict = self.data['caution_dict']
        if member in caution_dict:
            caution_dict[member] += 1
        else:
            caution_dict[member] = 1

        await self.data['sent_msg']['Caution'].edit(embed=self.get_embed(), view=self)


@app_commands.guild_only()
class Member(commands.GroupCog, name='멤버'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.GroupCog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user and message.content == '경고를 줄 멤버를 선택해요':
            await Caution.from_message(message, self.bot)

    @app_commands.command(name='경고', description='경고를 줄 멤버를 선택해요')
    async def caution(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await Caution.from_interaction(interaction, self.bot)


async def setup(bot: commands.Bot):
    await bot.add_cog(Member(bot))