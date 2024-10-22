import unittest
from unittest.mock import Mock, AsyncMock, patch
from ser_gawain.commands.crafting import Crafting


class MockRow(dict):
    def __getitem__(self, key):
        return super().__getitem__(key)


class TestCrafting(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = Mock()
        self.crafting = Crafting(self.bot)
        self.crafting.cursor = Mock()
        self.crafting.conn = Mock()
        self.accept_callback = self.crafting.accept.callback
        self.complete_callback = self.crafting.complete.callback

    @patch("discord.Interaction")
    async def test_accept_success(self, mock_interaction):
        mock_interaction.user.id = "12345"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        mock_job = MockRow({"requestor_id": "67890"})
        self.crafting.cursor.execute.return_value.fetchone.return_value = mock_job

        await self.accept_callback(self.crafting, mock_interaction, "1")

        self.crafting.cursor.execute.assert_called()
        self.crafting.conn.commit.assert_called()
        mock_interaction.followup.send.assert_called()

    @patch("discord.Interaction")
    async def test_accept_own_job(self, mock_interaction):
        mock_interaction.user.id = "12345"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        mock_job = MockRow({"requestor_id": "12345"})
        self.crafting.cursor.execute.return_value.fetchone.return_value = mock_job

        await self.accept_callback(self.crafting, mock_interaction, "1")

        mock_interaction.followup.send.assert_called_with(
            "You cannot accept your own crafting job.", ephemeral=True
        )

    @patch("discord.Interaction")
    async def test_complete_success(self, mock_interaction):
        mock_interaction.user.id = "12345"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        mock_job = MockRow({"accepted_by": "12345", "requestor_id": "67890"})
        self.crafting.cursor.execute.return_value.fetchone.return_value = mock_job
        self.crafting.conn.commit = AsyncMock()

        await self.complete_callback(self.crafting, mock_interaction, "1")

        self.crafting.cursor.execute.assert_called()
        self.crafting.conn.commit.assert_called()
        mock_interaction.followup.send.assert_called()

    @patch("discord.Interaction")
    async def test_complete_not_accepted_by_user(self, mock_interaction):
        mock_interaction.user.id = "12345"
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()

        mock_job = MockRow({"accepted_by": "67890", "requestor_id": "11111"})
        self.crafting.cursor.execute.return_value.fetchone.return_value = mock_job

        await self.complete_callback(self.crafting, mock_interaction, "1")

        mock_interaction.followup.send.assert_called_with(
            "You are not the one who accepted this job. Only the person who accepted the job can complete it.",
            ephemeral=True,
        )


if __name__ == "__main__":
    unittest.main()
