import asyncio

import discord
from discord import app_commands
from discord.ext import commands


class Caution(discord.ui.View):
    data: dict[int, list[dict[discord.Member, int] | discord.Message]] = {}
    def __init__(self, message: discord.Message):
        super().__init__(timeout=None)
        self.trigger_msg = message
        self.recent_member = message.author
        user_select = discord.ui.UserSelect(
            placeholder='경고를 줄 멤버를 선택해요',
            row=0,
        ) 
        user_select.callback = self.callback
        self.add_item(user_select)

    @classmethod
    async def from_message(cls, message: discord.Message):
        if not message.guild.id in cls.data:
            cls.data[message.guild.id] = []
            cls.data[message.guild.id].append({})
        else:
            asyncio.run_coroutine_threadsafe(cls.data[message.guild.id][1].delete(), asyncio.get_event_loop())
            del cls.data[message.guild.id][1]

        caution = cls(message)
        cls.data[message.guild.id].append(await message.channel.send(embed=caution.get_embed(), view=caution))

        return caution
    
    def get_embed(self):
        embed = discord.Embed(
            color=discord.Color.blurple(),
            title='⚠️  경고',
        )
        embed.set_thumbnail(url=self.recent_member.display_avatar.url)
        embed.add_field(name='', value='', inline=False)

        if Caution.data[self.trigger_msg.guild.id][0]:
            embed.description = '경고를 받은 멤버목록이에요\n\n쫓겨나지 않게 조심해야 해요'
            for member, count in Caution.data[self.trigger_msg.guild.id][0].items():
                embed.add_field(
                    name=f'{member.display_name}({member})',
                    value=f'경고 {count}회',
                    inline=False
                )
        else:
            embed.description = '경고받은 멤버가 없어요\n\n심심한 곳이네요'

        embed.set_footer(text=self.recent_member, icon_url=self.recent_member.display_avatar.url)

        return embed
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.recent_member = interaction.user

        if not self.children[0].values[0] in Caution.data[self.trigger_msg.guild.id][0]:
            Caution.data[self.trigger_msg.guild.id][0][self.children[0].values[0]] = 1
        else:
            Caution.data[self.trigger_msg.guild.id][0][self.children[0].values[0]] += 1

        await Caution.data[self.trigger_msg.guild.id][1].edit(embed=self.get_embed(), view=self)


@app_commands.guild_only()
class Member(commands.GroupCog, name='멤버'):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='경고', description='경고를 줄 멤버를 선택해요')
    async def warning(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await interaction.delete_original_response()
        ctx = await commands.Context.from_interaction(interaction)
        await Caution.from_message(ctx.message)


async def setup(bot: commands.Bot):
    await bot.add_cog(Member(bot))