import asyncio

import discord
from discord.ext import commands

import config


TEST_GUILD_ID_1 = discord.Object(id=1202849468681289728)
TEST_GUILD_ID_2 = discord.Object(id=1229731635730059325)


class NLPBot(commands.Bot):
    async def setup_hook(self):
        for cog in config.cogs_list:
            await self.load_extension(f'cogs.{cog}')

        self.tree.copy_global_to(guild=TEST_GUILD_ID_1)
        await self.tree.sync(guild=TEST_GUILD_ID_1)
        self.tree.copy_global_to(guild=TEST_GUILD_ID_2)
        await self.tree.sync(guild=TEST_GUILD_ID_2)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        print(f'[{message.channel.name}] {message.author.display_name}({message.author.name}): {message.content}')
        #await self.process_commands(message)


async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    async with NLPBot(commands.when_mentioned, intents=intents) as bot:
        await bot.start(config.token)


if __name__ == '__main__':
    asyncio.run(main())