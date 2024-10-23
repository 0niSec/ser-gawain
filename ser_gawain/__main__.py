import sqlite3
import discord
import logging
import os
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()


def find_roles_channel(guild: discord.Guild) -> discord.TextChannel:
    for channel in guild.channels:
        if isinstance(channel, discord.TextChannel) and channel.name == "roles":
            return channel
    return None


GUILD_ID = discord.Object(id=int(os.getenv("GUILD_ID")))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DESCRIPTION = "Ser Gawain is a New World Aeternum bot that handles Company crafting requests and more."

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")


class Gawain(commands.Bot):
    def __init__(self, *, intents=discord.Intents):
        super().__init__(command_prefix="", intents=intents, description=DESCRIPTION)
        self.session = None
        try:
            self.conn = sqlite3.connect(
                "gawain.db", check_same_thread=False, timeout=30.0
            )
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

        # Copy the commands to the guild
        self.tree.copy_global_to(guild=GUILD_ID)
        await self.tree.sync(guild=GUILD_ID)

    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        roles_channel = find_roles_channel(self.get_guild(int(os.getenv("GUILD_ID"))))
        if roles_channel:
            role_embed = discord.Embed(
                title="Crafting Roles",
                description="React to any of the emojis below to get the corresponding crafter role. Crafter roles will be pinged whenever someone makes a `/crafting request`.\n\n**Note:** This can possibly result in a lot of pings. Be sure you are wanting to help out or are OK being pinged possibly multiple times a day.",
                color=discord.Color.blurple(),
            )

            role_embed.add_field(
                name="Roles",
                value=f"\n\n<:arcana:1297648807030554724> Arcana\n<:armoring:1297648797886844999> Armoring\n<:cooking:1297648788399329361> Cooking\n<:engineering:1297648777372504075> Engineering\n<:furnishing:1297648768476516434> Furnishing\n<:jewelcrafting:1297648758921760829> Jewelcrafting\n<:weaponsmithing:1297648745969877052> Weaponsmithing",
                inline=False,
            )

            role_message = await roles_channel.send(embed=role_embed)
            await role_message.add_reaction("<:arcana:1297648807030554724>")
            await role_message.add_reaction("<:armoring:1297648797886844999>")
            await role_message.add_reaction("<:cooking:1297648788399329361>")
            await role_message.add_reaction("<:engineering:1297648777372504075>")
            await role_message.add_reaction("<:furnishing:1297648768476516434>")
            await role_message.add_reaction("<:jewelcrafting:1297648758921760829>")
            await role_message.add_reaction("<:weaponsmithing:1297648745969877052>")
            role_message = "React to this message for crafting roles"
        else:
            role_message = "No roles channel found"
            logging.error("No roles channel found")
            print("No roles channel found")

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


@bot.tree.command(name="reload", description="Reload the bot commands")
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


@bot.event
async def on_raw_reaction_add(payload):
    if payload.member.bot:
        return

    roles_channel = find_roles_channel(bot.get_guild(payload.guild_id))
    if roles_channel and payload.channel_id == roles_channel.id:
        message = await roles_channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if str(reaction.emoji) == str(payload.emoji):
                role = discord.utils.get(
                    payload.member.guild.roles, name=reaction.emoji.name
                )
                if role:
                    await payload.member.add_roles(role)
                break


@bot.event
async def on_raw_reaction_remove(payload):
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)

    if member is None:
        # Attempt to fetch the member if not in cache
        try:
            member = await guild.fetch_member(payload.user_id)
        except discord.errors.NotFound:
            logging.error(f"Member {payload.user_id} not found in the guild.")
            return

    if member.bot:
        return

    roles_channel = find_roles_channel(guild)
    if roles_channel and payload.channel_id == roles_channel.id:
        message = await roles_channel.fetch_message(payload.message_id)
        for reaction in message.reactions:
            if str(reaction.emoji) == str(payload.emoji):
                role = discord.utils.get(guild.roles, name=reaction.emoji.name)
                if role:
                    await member.remove_roles(role)
                break


# Run the bot
bot.run(DISCORD_TOKEN, log_handler=handler, log_level=logging.INFO)
