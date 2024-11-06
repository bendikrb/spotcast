"""Module the SpotifyDevice media player"""

from logging import getLogger

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    STATE_UNAVAILABLE
)

from custom_components.spotcast.media_player import MediaPlayer
from custom_components.spotcast.spotify import SpotifyAccount
from custom_components.spotcast import DOMAIN

LOGGER = getLogger(__name__)


class SpotifyDevice(MediaPlayer, MediaPlayerEntity):
    """Representation of a device in spotify"""

    INTEGRATION = DOMAIN

    def __init__(self, account: SpotifyAccount, device_data: dict):
        """Initialize the spotify device"""
        self._device_data: dict = device_data
        self._account: SpotifyAccount = account
        self.entity_id = self._define_entity_id()
        self._is_unavailable = False
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.id)},
            manufacturer="Spotify AB",
            model=f"Spotify Connect {self._device_data['type']}",
            name=f"Spotcast - {self.name} ({self._account.name})",
        )

    @property
    def unique_id(self) -> str:
        return f"{self.id}_{self._account.id}_spotcast_device"

    @property
    def id(self) -> str:
        return self._device_data["id"]

    @property
    def name(self):
        name = self._device_data["name"]
        return f"Spotcast ({self._account.name}) - {name}"

    @property
    def state(self):

        if self._is_unavailable:
            return STATE_UNAVAILABLE

        is_active = self._device_data["is_active"]

        return STATE_ON if is_active else STATE_OFF

    def _define_entity_id(self):

        removals = "()"

        name: str = self._device_data["name"]

        name = name.lower()
        name = name.replace(" ", "_")

        for char in removals:
            name = name.replace(char, "")

        return f"media_player.{name}_{self._account.id}_spotcast"

    async def async_update(self):
        """Updates the device information from the account"""

        if self._is_unavailable:
            LOGGER.debug("%s is unavailable, skipping update", self.entity_id)
            return

        LOGGER.debug("Updating device data for %s", self.entity_id)

        devices = await self._account.async_devices()

        for device in devices:
            if device["id"] == self.id:
                self._device_data = device
                return

        LOGGER.warn(
            "%s is no longer part of %s's Spotify Devices",
            self.entity_id,
            self._account.name
        )