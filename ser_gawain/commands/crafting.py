from datetime import datetime
import discord
import sqlite3
import logging
from enum import Enum
from typing import Optional
from discord.ext import commands
from discord import app_commands


async def accept_request(
    cursor: sqlite3.Cursor, user_id: int, request_id: str
) -> tuple[bool, str]:
    try:
        # Check if the job is available for acceptance
        job = cursor.execute(
            "SELECT requestor_id FROM crafting_requests WHERE request_id = ? AND status = 'PENDING'",
            (request_id,),
        ).fetchone()

        if not job:
            return (
                False,
                f"Crafting request {request_id} is not available. It may have already been accepted or cancelled.",
            )

        requestor_id = job["requestor_id"]

        if requestor_id == str(user_id):
            return False, "You cannot accept your own crafting request."

        # Update the job status
        cursor.execute(
            "UPDATE crafting_requests SET status = 'ACCEPTED', accepted_by = ? WHERE request_id = ?",
            (user_id, request_id),
        )
        cursor.connection.commit()

        return True, f"Crafting request {request_id} has been accepted"

    except sqlite3.DataError as e:
        logging.error(f"Error accepting crafting request {request_id}: {e}")
        return (
            False,
            f"Error accepting crafting request {request_id}. Please check the job ID and try again.",
        )


async def cancel_request(
    cursor: sqlite3.Cursor, user_id: int, request_id: str
) -> tuple[bool, str]:
    try:
        # Check if the job is available for cancellation
        job = cursor.execute(
            "SELECT requestor_id FROM crafting_requests WHERE request_id = ? AND status = 'PENDING' OR status = 'ACCEPTED'",
            (request_id,),
        ).fetchone()

        if not job:
            return (
                False,
                f"Crafting request {request_id} is not available for cancellation. It may have been already accepted or cancelled.",
            )

        requestor_id = job["requestor_id"]

        if requestor_id != str(user_id):
            return False, "You can only cancel your own crafting requests."

        # Update the job status
        cursor.execute(
            "UPDATE crafting_requests SET status = 'CANCELLED' WHERE request_id = ?",
            (request_id,),
        )

        cursor.connection.commit()

        return True, f"Crafting request {request_id} has been cancelled."

    except sqlite3.DataError as e:
        logging.error(f"Error with the data provided {request_id}: {e}")
        return (
            False,
            f"Error cancelling crafting request {request_id}. Please check the request ID and try again.",
        )
    except sqlite3.DatabaseError as e:
        logging.error(f"Error cancelling crafting request {request_id}: {e}")
        return (
            False,
            f"Error cancelling crafting request {request_id}. Please check the request ID and try again.",
        )


class TradeSkill(Enum):
    ARCANA = "Arcana"
    ARMORING = "Armoring"
    COOKING = "Cooking"
    ENGINEERING = "Engineering"
    FURNISHING = "Furnishing"
    JEWELCRAFTING = "Jewelcrafting"
    WEAPONSMITHING = "Weaponsmithing"


class Status(Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class RequestAcceptButton(discord.ui.Button):
    def __init__(self, request_id: str):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="✅",
        )
        self.request_id = request_id

    async def callback(self, interaction: discord.Interaction):
        # await interaction.response.defer(ephemeral=True)

        # https://discordpy.readthedocs.io/en/stable/ext/commands/cogs.html?highlight=get_cog#using-cogs
        # Used as a way to share data between the callback and the button
        # This was the best way without using a classmethod or staticmethod
        cog = interaction.client.get_cog("Crafting")
        success, message = await accept_request(
            cog.cursor, interaction.user.id, self.request_id
        )
        await interaction.response.send_message(
            f"{message} by {interaction.user.mention}!" if success else message,
            ephemeral=True,
        )


class RequestCancelButton(discord.ui.Button):
    def __init__(self, request_id: str):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="❌",
        )
        self.request_id = request_id

    async def callback(self, interaction: discord.Interaction):
        # await interaction.response.defer()

        cog = interaction.client.get_cog("Crafting")
        success, message = await cancel_request(
            cog.cursor, interaction.user.id, self.request_id
        )
        await interaction.response.send_message(
            f"{message}" if success else message,
            ephemeral=True,
        )


class RequestOpenThreadButton(discord.ui.Button):
    def __init__(self, request_id: str, item_name: str):
        super().__init__(
            style=discord.ButtonStyle.primary,
            emoji="🧵",
        )
        self.request_id = request_id
        self.item_name = item_name

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cog = interaction.client.get_cog("Crafting")

        # Get the requestor's user object
        requestor_id = cog.cursor.execute(
            "SELECT requestor_id FROM crafting_requests WHERE request_id = ?",
            (self.request_id,),
        ).fetchone()

        requestor_user = await cog.bot.fetch_user(int(requestor_id[0]))

        # Only another interested person can open the thread, not the requestor
        if interaction.user.id == int(requestor_id[0]):
            await interaction.followup.send(
                "Threads can only be opened by interested crafters, not the requestor. Please wait for someone else to  accept your request.",
                ephemeral=True,
            )
            return

        # Thread creation process
        try:
            thread = await interaction.message.create_thread(
                name=f"Request #{self.request_id} | {self.item_name}",
                reason=f"Create thread for crafting request {self.request_id}",
            )

            await thread.add_user(requestor_user)
            await thread.add_user(interaction.user)
            await thread.send(
                f"Thread requested by {interaction.user.mention}. Please use this thread to discuss the crafting request with the requestor."
            )

            await interaction.followup.send(
                f"Thread created for request {self.request_id}.",
                ephemeral=True,
            )
        except discord.errors.HTTPException as e:
            logging.error(
                f"Failed to create thread for request {self.request_id}. Reason: {e}"
            )
            await interaction.followup.send(
                f"Failed to create thread for request {self.request_id}. Reason: {e}",
                ephemeral=True,
            )
            return

        # Thread cleanup process
        try:
            await thread.leave()
        except discord.errors.HTTPException as e:
            logging.error(
                f"Failed to leave thread for request {self.request_id}. Reason: {e}"
            )


class RequestView(discord.ui.View):
    def __init__(self, request_id: str, item_name: str):
        super().__init__(timeout=30.0)
        self.add_item(RequestAcceptButton(request_id))
        self.add_item(RequestCancelButton(request_id))
        self.add_item(RequestOpenThreadButton(request_id, item_name))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)


class Crafting(commands.GroupCog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = self.bot.conn
        self.cursor = self.bot.cursor

    def cog_unload(self):
        self.conn.close()

    @app_commands.command(name="request", description="Make a crafting request")
    @app_commands.describe(
        item="The item to craft",
        amount="The amount of the item to craft",
        has_materials="Whether the materials are already owned",
        skill="The trade skill to use",
        level_required="The level required for the trade skill",
    )
    async def request(
        self,
        interaction: discord.Interaction,
        item: str,
        has_materials: bool,
        amount: Optional[int] = 1,
        skill: Optional[TradeSkill] = None,
        level_required: Optional[int] = None,
    ):
        """Make a crafting request"""
        requestor_id = interaction.user.id
        user_name = interaction.user.name

        try:
            # Check if the user exists in the users table, if not, add them
            self.cursor.execute(
                "SELECT * FROM users WHERE user_id = ?", (requestor_id,)
            )
            if self.cursor.fetchone() is None:
                self.cursor.execute(
                    "INSERT INTO users (user_id, user_name) VALUES (?, ?)",
                    (requestor_id, user_name),
                )
                self.conn.commit()

            # Add to the crafting requests table
            self.cursor.execute(
                "INSERT INTO crafting_requests (requestor_id, user_name, item_name, has_materials, amount, trade_skill, level_required, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    requestor_id,
                    user_name,
                    item,
                    has_materials,
                    amount,
                    skill.value if skill else None,
                    level_required,
                    "PENDING",
                ),
            )

            # Commit the changes to the database
            self.conn.commit()

            # Get the job ID
            request_id = self.cursor.lastrowid

            # Log the request
            logging.info(
                f"User {user_name} ({requestor_id}) created a crafting request for {item} with amount {amount} and skill {skill} and level {level_required}"
            )

            # Get the role for the skill if it exists
            skill_role = None
            if skill:
                skill_role = discord.utils.get(
                    interaction.guild.roles, name=skill.value.lower()
                )

            # Create the Embed with View
            request_embed = discord.Embed(
                title="Crafting Request",
                color=discord.Color.gold(),
            )

            request_embed.add_field(
                name=f"Crafting Request",
                value=f"**ID:** {request_id}\n**Item:** {item}\n**Amount:** {amount}\n**Has Materials:** {has_materials}\n**Trade Skill:** {skill.value if skill else 'None'}\n**Level Required:** {level_required}",
            )

            request_view = RequestView(str(request_id), item)

            await interaction.response.send_message(
                embed=request_embed, view=request_view
            )

            if skill_role is not None:
                await interaction.channel.send(f"<@&{skill_role.id}>")

            # Set the message attribute of the dropdown view to the original response
            # We need to do this in order to edit the message later for timeout
            request_view.message = await interaction.original_response()

        except sqlite3.Error as e:
            logging.error(f"Database error in request command: {e}")
            await interaction.response.send_message(
                "An error occurred while creating your request. Please try again.",
                ephemeral=True,
            )
        except Exception as e:
            logging.error(f"Unexpected error in request command: {e}")
            await interaction.response.send_message(
                "An unexpected error occurred. Please try again.", ephemeral=True
            )

    @app_commands.command(
        name="status",
        description="Check the status of a specific crafting request by ID",
    )
    async def status(self, interaction: discord.Interaction, request_id: str):
        """Check the status of a crafting request"""
        await interaction.response.defer()

        # Check if the request exists
        try:
            self.cursor.execute(
                "SELECT user_name, item_name, amount, trade_skill, level_required, status, CASE WHEN has_materials = 0 THEN 'Yes' ELSE 'No' END as has_materials FROM crafting_requests WHERE request_id = ?",
                (request_id,),
            )
            request = self.cursor.fetchone()

            if request is None:
                await interaction.followup.send(
                    f"Crafting request {request_id} not found."
                )
                return

            # Construct the embed
            status_embed = discord.Embed(
                title="Crafting Request Status",
                description=f"Status of crafting request {request_id}:",
                color=discord.Color.dark_orange(),
            )

            status_embed.add_field(
                name="Requestor",
                value=f"{request["user_name"]}",
                inline=False,
            )

            status_embed.add_field(
                name="Item",
                value=f"{request['item_name']}",
                inline=False,
            )

            status_embed.add_field(
                name="Has Materials",
                value=f"{request['has_materials']}",
                inline=False,
            )

            status_embed.add_field(
                name="Amount",
                value=f"{request['amount']}",
                inline=False,
            )

            status_embed.add_field(
                name="Trade Skill",
                value=f"{request['trade_skill']}",
                inline=True,
            )

            status_embed.add_field(
                name="Level Required",
                value=f"{request['level_required']}",
                inline=True,
            )

            status_embed.add_field(
                name="Status",
                value=f"{request['status']}",
                inline=False,
            )

            await interaction.followup.send(embed=status_embed)

        except sqlite3.DatabaseError as e:
            logging.error(f"Database error in status command: {e}")
            await interaction.followup.send(
                "An error occurred while checking the status of the crafting request. Please try again.",
                ephemeral=True,
            )
        except discord.errors.HTTPException as e:
            logging.error(f"Error in sending message: {e}")
            await interaction.followup.send(
                "An error occurred while sending the status message. Please try again.",
                ephemeral=True,
            )

    @app_commands.command(name="cancel", description="Cancel a crafting request")
    async def cancel(self, interaction: discord.Interaction, request_id: int):
        """Cancel a crafting request"""

        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        success, message = await cancel_request(self.cursor, user_id, request_id)

        if success:
            await interaction.followup.send(
                f"{message}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="list", description="List crafting requests")
    @app_commands.describe(
        status="The status of the crafting request to list",
    )
    async def list(self, interaction: discord.Interaction, status: Optional[Status]):
        """List crafting requests by status"""

        await interaction.response.defer()

        if status:
            try:
                self.cursor.execute(
                    "SELECT request_id, user_name, item_name, CASE WHEN has_materials = 0 THEN 'Yes' ELSE 'No' END as has_materials, amount, status FROM crafting_requests WHERE status = ?",
                    (status.value.upper(),),
                )
                jobs = self.cursor.fetchall()

                jobs_embed = discord.Embed(
                    title="Crafting Requests",
                    description="List of crafting requests",
                    color=discord.Color.gold(),
                )

                for job in jobs:
                    jobs_embed.add_field(
                        name=f"Job ID: {job['request_id']}",
                        value=f"**User:** {job['user_name']}\n**Item:** {job['item_name']}\n**Has Materials:** {job['has_materials']}\n**Amount:** {job['amount']}\n**Status:** {job['status']}",
                        inline=True,
                    )

                await interaction.followup.send(embed=jobs_embed)
            except sqlite3.DatabaseError as e:
                logging.error(f"Database error in list command: {e}")
                await interaction.followup.send(
                    "An error occurred while listing the crafting requests. Please try again.",
                    ephemeral=True,
                )
            except discord.errors.HTTPException as e:
                logging.error(f"Error in sending message: {e}")
                await interaction.followup.send(
                    "An error occurred while sending the list message. Please try again.",
                    ephemeral=True,
                )
        else:
            try:
                self.cursor.execute(
                    "SELECT request_id, user_name, item_name, CASE WHEN has_materials = 0 THEN 'Yes' ELSE 'No' END as has_materials, amount, status FROM crafting_requests",
                )
                jobs = self.cursor.fetchall()

                all_jobs_embed = discord.Embed(
                    title="Crafting Requests",
                    description="List of all crafting requests",
                    color=discord.Color.gold(),
                )

                for job in jobs:
                    all_jobs_embed.add_field(
                        name=f"Request ID: {job['request_id']}",
                        value=f"**User:** {job['user_name']}\n**Item:** {job['item_name']}\n**Has Materials:** {job['has_materials']}\n**Amount:** {job['amount']}\n**Status:** {job['status']}",
                        inline=True,
                    )

                await interaction.followup.send(embed=all_jobs_embed)
            except sqlite3.DatabaseError as e:
                logging.error(f"Database error in list command: {e}")
                await interaction.followup.send(
                    "An error occurred while listing the crafting requests. Please try again.",
                    ephemeral=True,
                )
            except discord.errors.HTTPException as e:
                logging.error(f"Error in sending message: {e}")
                await interaction.followup.send(
                    "An error occurred while sending the list message. Please try again.",
                    ephemeral=True,
                )

    @app_commands.command(name="accept", description="Accept a crafting request")
    async def accept(self, interaction: discord.Interaction, request_id: str):
        """Accept a crafting request"""
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True)

        success, message = await accept_request(self.cursor, user_id, request_id)

        if success:
            try:
                job = self.cursor.execute(
                    "SELECT requestor_id FROM crafting_requests WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                requestor_id = job["requestor_id"]
                await interaction.followup.send(
                    f"<@{requestor_id}> {message} by {interaction.user.mention}!",
                )
            except sqlite3.DatabaseError as e:
                logging.error(f"Database error in accept command: {e}")
                await interaction.followup.send(
                    "An error occurred while accepting the crafting request. Please try again.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(message, ephemeral=True)

    @app_commands.command(name="complete", description="Complete a crafting request")
    async def complete(self, interaction: discord.Interaction, request_id: str):
        """Complete a crafting request"""

        user_id = interaction.user.id

        await interaction.response.defer()

        # Get the job details matching the entered job ID
        try:
            job = self.cursor.execute(
                "SELECT * FROM crafting_requests WHERE request_id = ? AND status = 'ACCEPTED'",
                (request_id,),
            ).fetchone()

            # If the job exists and is not already completed
            if not job:
                await interaction.followup.send(
                    f"Crafting request {request_id} not found or already completed.",
                    ephemeral=True,
                )
                return

            # Check if the user who accepted the job is the same as the user who is completing the job
            if job["accepted_by"] != str(user_id):
                await interaction.followup.send(
                    f"You are not the one who accepted this job. Only the person who accepted the job can complete it.",
                    ephemeral=True,
                )
                return

            # Get who requested the crafting request to use later
            requestor_id: discord.User = job["requestor_id"]

            # Update the job status to "COMPLETED"
            current_time = datetime.now()
            self.cursor.execute(
                "UPDATE crafting_requests SET status = 'COMPLETED', completed_on = ? WHERE request_id = ?",
                (request_id, current_time),
            )

            self.cursor.execute(
                """UPDATE users 
                SET requests_completed = COALESCE(requests_completed, 0) + 1 
                WHERE user_id = ?
                """,
                (user_id),
            )

            await self.conn.commit()

            await interaction.followup.send(
                f"<@{requestor_id}> Crafting request {request_id} has been completed by {interaction.user.mention}"
            )

            logging.info(
                f"Crafting request {request_id} completed by {interaction.user.name} at {current_time}"
            )
        except sqlite3.DatabaseError as e:
            logging.error(f"Database error in complete command: {e}")
            await interaction.followup.send(
                "An error occurred while completing the crafting request. Please try again.",
                ephemeral=True,
            )
        except discord.errors.HTTPException as e:
            logging.error(f"Error in sending message: {e}")
            await interaction.followup.send(
                "An error occurred while sending the message. Please try again.",
                ephemeral=True,
            )

    @app_commands.command(name="set_skill", description="Set a trade skill")
    async def set_skill(
        self, interaction: discord.Interaction, skill: TradeSkill, skill_level: int
    ):
        """Set a trade skill"""

        user_id = interaction.user.id

        try:
            self.cursor.execute(
                "INSERT INTO trade_skills (user_id, user_name, skill_name, skill_level) VALUES (?, ?, ?, ?) ON CONFLICT (user_id, skill_name) DO UPDATE SET skill_level = ?",
                (user_id, interaction.user.name, skill.value, skill_level, skill_level),
            )
            self.conn.commit()

            await interaction.response.send_message(
                f"Trade skill {skill.value} set to {skill_level}!", ephemeral=True
            )
        except sqlite3.DatabaseError as e:
            logging.error(f"Database error in set_skill command: {e}")
            await interaction.response.send_message(
                "An error occurred while setting the trade skill. Please try again.",
                ephemeral=True,
            )
        except discord.errors.HTTPException as e:
            logging.error(f"Error in sending message: {e}")
            await interaction.response.send_message(
                "An error occurred while sending the message. Please try again.",
                ephemeral=True,
            )

    @app_commands.command(
        name="crafters", description="List crafters with their trained skills"
    )
    async def crafters(self, interaction: discord.Interaction):
        """List crafters with their trained skills"""
        await interaction.response.defer()

        # Fetch crafters and their trained skills
        try:
            self.cursor.execute(
                "SELECT user_name, GROUP_CONCAT(skill_name || ': ' || skill_level, ', ') AS skills FROM trade_skills GROUP BY user_id, user_name"
            )
            crafters = self.cursor.fetchall()

            if not crafters:
                await interaction.response.send_message(
                    "No crafters found. Use `/set_skill` to set a trade skill.",
                    ephemeral=True,
                )

            crafters_embed = discord.Embed(
                title="Crafters",
                description="List of crafters with their trained skills",
                color=discord.Color.green(),
            )

            for crafter in crafters:
                crafters_embed.add_field(
                    name=f"Crafter: {crafter[0].capitalize()}",
                    value=f"**Skills:** {crafter[1]}",
                    inline=False,
                )

            await interaction.followup.send(embed=crafters_embed)
        except sqlite3.DatabaseError as e:
            logging.error(f"Database error in crafters command: {e}")
            await interaction.response.send_message(
                "An error occurred while fetching crafters. Please try again.",
                ephemeral=True,
            )
        except discord.errors.HTTPException as e:
            logging.error(f"Error in sending message: {e}")
            await interaction.response.send_message(
                "An error occurred while sending the message. Please try again.",
                ephemeral=True,
            )

    @app_commands.command(name="delete", description="Delete a crafting request")
    @app_commands.default_permissions(administrator=True)
    async def delete(self, interaction: discord.Interaction, request_id: str):
        """Delete a crafting request"""
        await interaction.response.defer(ephemeral=True)

        try:
            self.cursor.execute(
                "DELETE FROM crafting_requests WHERE request_id = ?", (request_id,)
            )
            self.conn.commit()
            await interaction.response.send_message(
                f"Crafting request {request_id} has been deleted!", ephemeral=True
            )
            logging.info(
                f"Crafting request {request_id} has been deleted by {interaction.user.id}({interaction.user.name})!"
            )
        except sqlite3.DatabaseError as e:
            logging.error(f"Error deleting crafting request {request_id}: {e}")
            await interaction.followup.send(
                f"Error deleting crafting request {request_id}. Make sure that the `request_id` is correct and try again.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Crafting(bot))
