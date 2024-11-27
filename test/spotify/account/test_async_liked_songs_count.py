"""Module to test the async_playlists function"""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch, AsyncMock
from time import time

from custom_components.spotcast.spotify.account import (
    SpotifyAccount,
    OAuth2Session,
    InternalSession,
    HomeAssistant,
)

TEST_MODULE = "custom_components.spotcast.spotify.account"


class TestDatasetExpired(IsolatedAsyncioTestCase):

    @patch.object(SpotifyAccount, "_async_get_count")
    @patch(f"{TEST_MODULE}.Spotify")
    async def asyncSetUp(
            self,
            mock_spotify: MagicMock,
            mock_pager: MagicMock,
    ):

        self.mocks = {
            "internal": MagicMock(spec=InternalSession),
            "external": MagicMock(spec=OAuth2Session),
            "hass": MagicMock(spec=HomeAssistant),
            "pager": mock_pager,
        }
        self.mocks["hass"].loop = MagicMock()

        self.mock_spotify = mock_spotify

        self.mocks["external"].token = {
            "access_token": "12345",
            "expires_at": 12345.61,
        }

        self.account = SpotifyAccount(
            entry_id="12345",
            hass=self.mocks["hass"],
            external_session=self.mocks["external"],
            internal_session=self.mocks["internal"],
            is_default=True
        )

        self.account.async_ensure_tokens_valid = AsyncMock()

        self.account._datasets["profile"].expires_at = time() + 9999
        self.account._datasets["profile"]._data = {"name": "Dummy"}
        self.account._datasets["liked_songs"].expires_at = time() - 9999
        self.account._datasets["liked_songs"]._data = [
            {"track": {"uri": "foo"}},
            {"track": {"uri": "bar"}},
        ]
        self.mocks["pager"].return_value = 3
        self.result = await self.account.async_liked_songs_count()

    def test_profile_retrieved_was_expected(self):
        self.assertEqual(self.result, 3)