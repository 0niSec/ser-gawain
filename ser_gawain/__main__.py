import asyncio
import asqlite
import discord
import logging
import os
from discord.ext import commands
from discord.app_commands import CommandTree
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler


load_dotenv()


GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DESCRIPTION = "Ser Gawain is a New World Aeternum bot that handles Company crafting requests and more."

# Create formatters and handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# File handler with rotation
file_handler = RotatingFileHandler(
    filename="discord.log",
    encoding="utf-8",
    mode="w",
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
)
file_handler.setFormatter(formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Discord logger specific configuration
discord_logger = logging.getLogger("discord")
discord_logger.setLevel(logging.INFO)


class GawainTree(CommandTree):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.channel.type == discord.ChannelType.public_thread:
            await interaction.response.send_message(
                "This command cannot be used in a thread.", ephemeral=True
            )
            return False
        else:
            return True


class Gawain(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(
            command_prefix="",
            intents=intents,
            description=DESCRIPTION,
            tree_cls=GawainTree,
        )
        self.conn = None

    async def setup_hook(self):
        self.conn = await asqlite.connect("gawain.db")
        await self.create_tables()

        # Load Extensions
        await self.load_extension("commands.crafting")
        await self.load_extension("commands.users")

    async def create_tables(self):
        async with self.conn.cursor() as cursor:
            await cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    user_name TEXT,
                    requests_completed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS crafting_requests (
                    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requestor_id TEXT,
                    user_name TEXT,
                    item_name TEXT,
                    has_materials BOOLEAN,
                    amount INTEGER,
                    trade_skill TEXT,
                    level_required INTEGER CHECK(level_required >= 0 AND level_required <= 250),
                    status TEXT,
                    accepted_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_on TIMESTAMP DEFAULT NULL,
                    FOREIGN KEY (accepted_by) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS trade_skills (
                    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    user_name TEXT,
                    skill_name TEXT,
                    skill_level INTEGER CHECK(skill_level >= 0 AND skill_level <= 250),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE (user_id, skill_name)
                );
            """
            )
            await self.conn.commit()

    async def on_ready(self):
        logging.info(f"Logged on as {self.user}!")

    async def close(self):
        if self.conn:
            await self.conn.close()
        await super().close()


intents = discord.Intents.default()
intents.reactions = True
intents.message_content = True
intents.members = True

bot = Gawain(intents=intents)

# Run the bot
bot.run(DISCORD_TOKEN, log_level=logging.INFO)
