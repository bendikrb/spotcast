"""Controller to interface with Spotify."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import warnings
from typing import TYPE_CHECKING

import requests
from pychromecast.controllers import BaseController

from .const import APP_SPOTIFY
from .error import LaunchError

if TYPE_CHECKING:
    from pychromecast import Chromecast
    from pychromecast.controllers import CastMessage

APP_NAMESPACE = "urn:x-cast:com.spotify.chromecast.secure.v1"
TYPE_GET_INFO = "getInfo"
TYPE_GET_INFO_RESPONSE = "getInfoResponse"
TYPE_ADD_USER = "addUser"
TYPE_ADD_USER_RESPONSE = "addUserResponse"
TYPE_ADD_USER_ERROR = "addUserError"

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class SpotifyController(BaseController):
    """Controller to interact with Spotify namespace."""

    def __init__(
        self,
        cast_device: Chromecast,
        access_token: str | None = None,
        expires: int | None = None,
    ) -> None:
        super().__init__(APP_NAMESPACE, APP_SPOTIFY)

        self.client = None
        self.session_started = False
        self.access_token = access_token
        self.expires = expires
        self.is_launched = False
        self.device = None
        self.credential_error = False
        self.waiting = threading.Event()
        self.cast_device = cast_device

    def receive_message(self, _message: CastMessage, data: dict) -> bool:
        """Handle the auth flow and active player selection.

        Called when a message is received.
        """
        if data["type"] == TYPE_GET_INFO_RESPONSE:
            self.device = self.getSpotifyDeviceID()
            self.client = data["payload"]["clientID"]
            headers = {
                'authority': 'spclient.wg.spotify.com',
                'authorization': f'Bearer {self.access_token}',
                'content-type': 'text/plain;charset=UTF-8',
            }

            request_body = json.dumps({'clientId': self.client, 'deviceId': self.device})

            response = requests.post(
                'https://spclient.wg.spotify.com/device-auth/v1/refresh',
                headers=headers,
                data=request_body,
                timeout=10,
            )
            json_resp = response.json()
            self.send_message({
                "type": TYPE_ADD_USER,
                "payload": {
                    "blob": json_resp["accessToken"],
                    "tokenType": "accesstoken",
                }
            })
        if data["type"] == TYPE_ADD_USER_RESPONSE:
            self.is_launched = True
            self.waiting.set()

        if data["type"] == TYPE_ADD_USER_ERROR:
            self.device = None
            self.credential_error = True
            self.waiting.set()
        return True

    def launch_app(self, timeout: int = 10) -> None:
        """Launch Spotify application.

        Will raise a LaunchError exception if there is no response from the
        Spotify app within timeout seconds.
        """
        if self.access_token is None or self.expires is None:
            raise ValueError("access_token and expires cannot be empty")

        def callback() -> None:
            self.send_message({"type": TYPE_GET_INFO, "payload": {
                "remoteName": self.cast_device.cast_info.friendly_name,
                "deviceID": self.getSpotifyDeviceID(),
                "deviceAPI_isGroup": False,
            }})

        self.device = None
        self.credential_error = False
        self.waiting.clear()
        self.launch(callback_function=callback)

        counter = 0
        while counter < (timeout + 1):
            if self.is_launched:
                return
            self.waiting.wait(1)
            counter += 1

        if not self.is_launched:
            raise LaunchError(
                "Timeout when waiting for status response from Spotify app"
            )

    # pylint: disable=too-many-locals
    def quick_play(self, **kwargs) -> None:
        """Launch the spotify controller and returns when it's ready.

        To actually play media, another application using spotify connect is required.
        """
        self.access_token = kwargs["access_token"]
        self.expires = kwargs["expires"]

        self.launch_app(timeout=20)

    def getSpotifyDeviceID(self) -> str:  # noqa: N802
        """Retrieve the Spotify deviceID from provided chromecast info."""
        self.logger.info(
            "Usage of SpotifyController.getSpotifyDeviceID() is deprecated and will be removed in a future release."
            "Please use get_spotify_device_id instead."
        )
        warnings.warn(
            "You should use `get_spotify_device_id(), ...,"
            "additional_types=('track',))` instead",
            DeprecationWarning,
        )
        return self.get_spotify_device_id()

    def get_spotify_device_id(self) -> str:
        """Retrieve the Spotify deviceID from provided chromecast info."""
        return hashlib.md5(self.cast_device.cast_info.friendly_name.encode()).hexdigest()  # noqa: S324
