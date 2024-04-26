import asyncio

import discord
from discord.ext import commands

import config


TEST_GUILD_ID_LIST = [discord.Object(id=1202849468681289728), discord.Object(id=1229731635730059325), discord.Object(id=553237519991570453)]


class NLPBot(commands.Bot):
    def __init__(self, command_prefix, *, intents: discord.Intents):
        super().__init__(command_prefix, intents=intents)
        self.data: dict[int, dict[str, bool | int | float | list[dict[str, str]] | dict[discord.Member, int] | dict[str, discord.Message]]] = {}
        self.history: dict[str, dict[str, str]] = {}

    async def setup_hook(self):
        for cog in config.cogs_list:
            await self.load_extension(f'cogs.{cog}')

        for id in TEST_GUILD_ID_LIST:
            self.tree.copy_global_to(guild=id)
            await self.tree.sync(guild=id)

    async def on_ready(self):
        for guild in self.guilds:
            self.initialize_guild_data(guild.id)
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_guild_join(self, guild: discord.Guild):
        self.initialize_guild_data(guild.id)

    def initialize_guild_data(self, guild_id: int):
        if guild_id not in self.data:
            self.data[guild_id] = {}
            self.data[guild_id]['NLP'] = True
            self.data[guild_id]['repeat'] = 0
            self.data[guild_id]['volume'] = 0.1
            self.data[guild_id]['playlist'] = []
            self.data[guild_id]['caution_dict'] = {}
            self.data[guild_id]['sent_msg'] = {}


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    async with NLPBot(commands.when_mentioned, intents=intents) as bot:
        await bot.start(config.token)


if __name__ == '__main__':
    asyncio.run(main())