import sqlite3
import discord
import logging
import os
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()


GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DESCRIPTION = "Ser Gawain is a New World Aeternum bot that handles Company crafting requests and more."

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")


class Gawain(commands.Bot):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(command_prefix="", intents=intents, description=DESCRIPTION)
        self.session = None
        try:
            self.conn = sqlite3.connect("gawain.db", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.create_tables()
        except sqlite3.Error as e:
            logging.error(f"Database connection failed: {e}")
            raise RuntimeError("Failed to initialize database connection")

    def create_tables(self):
        self.cursor.executescript(
            """
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
        self.conn.commit()

    async def setup_hook(self):
        # Load Extensions
        await self.load_extension("commands.crafting")
        await self.load_extension("commands.users")

    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        logging.info(f"Logged on as {self.user}!")

    async def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        if self.session:
            await self.session.close()
        await super().close()


intents = discord.Intents.default()
intents.reactions = True
intents.message_content = True
intents.members = True

bot = Gawain(intents=intents)

bot.owner_id = os.getenv("OWNER_ID")


@bot.tree.command(name="reload", description="Reload the bot commands")
@commands.is_owner()
async def reload_extensions(interaction: discord.Interaction):
    """Reload the bot commands"""
    await interaction.response.defer(ephemeral=True)
    try:
        await bot.reload_extension("commands.crafting")
        await bot.reload_extension("commands.users")
    except Exception as e:
        await interaction.response.edit_message(
            content=f"Error reloading commands: {e}"
        )
    await interaction.followup.send("Commands reloaded!")


# Run the bot
bot.run(DISCORD_TOKEN, log_handler=handler, log_level=logging.INFO)
