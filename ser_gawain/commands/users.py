import discord
import sqlite3
import logging
from discord.ext import commands
from discord import app_commands


class Users(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect("gawain.db")
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                user_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )
        self.conn.commit()

    def cog_unload(self):
        self.conn.close()

    @app_commands.command(name="add", description="Adds a user to the database")
    @app_commands.default_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction):
        """Add a user to the database. Will only add the initiator of the command."""
        user_id = interaction.user.id
        user_name = interaction.user.name
        try:
            self.cursor.execute(
                "INSERT INTO users (user_id, user_name) VALUES (?, ?)",
                (user_id, user_name),
            )
            self.conn.commit()
            await interaction.response.send_message(
                f"User {user_name} added to the database!", ephemeral=True
            )

            logging.info(f"User {user_name} added to the database.")
        except sqlite3.IntegrityError:
            await interaction.response.send_message(
                "User already exists in the database.", ephemeral=True
            )
            logging.error(
                f"User {user_name} ({user_id}) already exists in the database."
            )
            return

    @app_commands.command(name="delete", description="Delete a user from the database")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, user: discord.User):
        """Delete a user from the database. Will only delete the initiator of the command."""
        user_id = user.id

        try:
            self.cursor.execute("DELETE FROM users WHERE user_id = ?", user_id)
            self.conn.commit()
            await interaction.response.send_message(
                f"User {user} has been deleted from the database!"
            )

            logging.info(f"User {user} has been deleted from the database.")

        except sqlite3.DatabaseError as e:
            await interaction.response.send_message(f"Error deleting user {user}: {e}")
            logging.error(f"Error deleting user {user}: {e}")
        except sqlite3.DataError as e:
            await interaction.response.send_message(f"Error deleting user {user}: {e}")
            logging.error(f"Error deleting user {user}: {e}")
        except sqlite3.Error as e:
            await interaction.response.send_message(f"Error deleting user {user}: {e}")
            logging.error(f"Error deleting user {user}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Users(bot))
