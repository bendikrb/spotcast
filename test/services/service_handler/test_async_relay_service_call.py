"""Module to test the async_relay_service_call"""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from custom_components.spotcast.services.service_handler import (
    ServiceHandler,
    HomeAssistant,
    ServiceCall,
    UnknownServiceError,
)

TEST_MODULE = "custom_components.spotcast.services.service_handler"


class TestServiceCall(IsolatedAsyncioTestCase):

    @patch(f"{TEST_MODULE}.async_play_media")
    async def asyncSetUp(self, mock_play_media: MagicMock):

        self.hass = MagicMock(spec=HomeAssistant)
        self.call = MagicMock(spec=ServiceCall)
        self.call.service = "play_media"
        self.mock_play_media = mock_play_media

        handler = ServiceHandler(self.hass)

        await handler.async_relay_service_call(self.call)

    async def test_async_play_media_was_called(self):
        try:
            self.mock_play_media.assert_called()
        except AssertionError:
            self.fail()

    async def test_async_play_received_hass_and_call(self):
        try:
            self.mock_play_media.assert_called_with(
                self.hass,
                self.call,
            )
        except AssertionError:
            self.fail()


class TestUnknownService(IsolatedAsyncioTestCase):

    async def test_error_raised(self):

        self.hass = MagicMock(spec=HomeAssistant)
        self.call = MagicMock(spec=ServiceCall)
        self.call.service = "unkown_service"

        handler = ServiceHandler(self.hass)

        with self.assertRaises(UnknownServiceError):
            await handler.async_relay_service_call(self.call)