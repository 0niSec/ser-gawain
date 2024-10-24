import discord
import sqlite3
import asqlite
import asyncio
import logging
from discord.ext import commands
from discord import app_commands


class Users(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.conn: asqlite.Connection = self.bot.conn

    async def cog_unload(self):
        await self.conn.close()

    @app_commands.command(name="add", description="Adds a user to the database")
    @app_commands.default_permissions(administrator=True)
    async def add(self, interaction: discord.Interaction):
        """Add a user to the database. Will only add the initiator of the command."""
        user_id = interaction.user.id
        user_name = interaction.user.name

        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO users (user_id, user_name) VALUES (?, ?)",
                    (user_id, user_name),
                )
                await self.conn.commit()

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

    @app_commands.command(name="delete", description="Delete a user from the database")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, user: discord.User):
        """Delete a user from the database. Will only delete the initiator of the command."""
        user_id = user.id

        try:
            async with self.conn.cursor() as cursor:
                await cursor.execute("DELETE FROM users WHERE user_id = ?", user_id)
                await self.conn.commit()

            await interaction.response.send_message(
                f"User {user} has been deleted from the database!"
            )

            logging.info(f"User {user} has been deleted from the database.")

        except sqlite3.DatabaseError as e:
            await interaction.response.send_message(f"Error deleting user {user}: {e}")
            logging.error(f"Error deleting user {user}: {e}")
        except sqlite3.Error as e:
            await interaction.response.send_message(
                f"Unknown error deleting user {user}: {e}"
            )
            logging.error(f"Unknown error deleting user {user}: {e}")

    @app_commands.command(
        name="requests_completed",
        description="Show the number of requests completed by a user",
    )
    async def requests_completed(
        self, interaction: discord.Interaction, user: discord.User
    ):
        """Show the number of requests completed by a user"""
        user_id = interaction.user.id

        async with self.conn.cursor() as cursor:
            result = await cursor.execute(
                "SELECT requests_completed FROM users WHERE user_id = ?", user_id
            )

            num_requests_completed = await cursor.fetchone()

        if result:
            requests_completed = result[0]
            await interaction.response.send_message(
                f"User {user} has completed {requests_completed} requests."
            )
        else:
            await interaction.response.send_message(
                f"User {user} has not completed any requests."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Users(bot))
