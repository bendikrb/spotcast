"""Main module for spotcast homeassistant utility."""

from __future__ import annotations

import logging
import time

from homeassistant.components import websocket_api
from homeassistant.const import CONF_ENTITY_ID, CONF_OFFSET, CONF_REPEAT
from homeassistant.core import HomeAssistant, ServiceCall, callback

from .const import (
    CONF_ACCOUNTS,
    CONF_DEVICE_NAME,
    CONF_FORCE_PLAYBACK,
    CONF_IGNORE_FULLY_PLAYED,
    CONF_RANDOM,
    CONF_SHUFFLE,
    CONF_SP_DC,
    CONF_SP_KEY,
    CONF_SPOTIFY_ACCOUNT,
    CONF_SPOTIFY_CATEGORY,
    CONF_SPOTIFY_COUNTRY,
    CONF_SPOTIFY_DEVICE_ID,
    CONF_SPOTIFY_LIMIT,
    CONF_SPOTIFY_SEARCH,
    CONF_SPOTIFY_URI,
    CONF_START_VOL,
    DOMAIN,
    SCHEMA_PLAYLISTS,
    SCHEMA_WS_ACCOUNTS,
    SCHEMA_WS_CASTDEVICES,
    SCHEMA_WS_DEVICES,
    SCHEMA_WS_PLAYER,
    SERVICE_START_COMMAND_SCHEMA,
    SPOTCAST_CONFIG_SCHEMA,
    WS_TYPE_SPOTCAST_ACCOUNTS,
    WS_TYPE_SPOTCAST_CASTDEVICES,
    WS_TYPE_SPOTCAST_DEVICES,
    WS_TYPE_SPOTCAST_PLAYER,
    WS_TYPE_SPOTCAST_PLAYLISTS,
)
from .helpers import (
    async_wrap,
    get_cast_devices,
    get_random_playlist_from_category,
    get_search_results,
    get_spotify_devices,
    get_spotify_install_status,
    get_spotify_media_player,
    is_empty_str,
    is_valid_uri,
)
from .spotcast_controller import SpotcastController

CONFIG_SCHEMA = SPOTCAST_CONFIG_SCHEMA

_LOGGER = logging.getLogger(__name__)


def setup(hass: HomeAssistant, config) -> bool:
    """Set up integration with Home Assistant."""
    # get spotify core integration status
    # if return false, could indicate a bad spotify integration. Race
    # condition doesn't permit us to abort setup, see #258
    if not get_spotify_install_status(hass):
        _LOGGER.debug(
            "Spotify integration was not found, please verify integration is "
            "functionnal. Could result in python error..."
        )

    # Setup the Spotcast service.
    conf = config[DOMAIN]

    sp_dc = conf[CONF_SP_DC]
    sp_key = conf[CONF_SP_KEY]
    accounts = conf.get(CONF_ACCOUNTS)

    sc_controller = SpotcastController(hass, sp_dc, sp_key, accounts)

    hass.data.setdefault(DOMAIN, {})["controller"] = sc_controller

    @callback
    def websocket_handle_playlists(hass: HomeAssistant, connection, msg) -> None:
        @async_wrap
        def get_playlist() -> None:
            """Handle to get .playlist."""
            playlist_type = msg.get("playlist_type")
            country_code = msg.get("country_code")
            locale = msg.get("locale", "en")
            limit = msg.get("limit", 10)
            account = msg.get("account", None)

            _LOGGER.debug("websocket_handle_playlists msg: %s", msg)
            resp = sc_controller.get_playlists(
                account, playlist_type, country_code, locale, limit
            )
            connection.send_message(websocket_api.result_message(msg["id"], resp))

        hass.async_add_job(get_playlist())

    @callback
    def websocket_handle_devices(hass: HomeAssistant, connection, msg) -> None:
        @async_wrap
        def get_devices() -> None:
            """Handle to get devices. Only for default account."""
            account = msg.get("account", None)
            client = sc_controller.get_spotify_client(account)
            me_resp = client._get("me")  # pylint: disable=W0212  # noqa: SLF001
            spotify_media_player = get_spotify_media_player(hass, me_resp["id"])
            resp = get_spotify_devices(spotify_media_player)
            connection.send_message(websocket_api.result_message(msg["id"], resp))

        hass.async_add_job(get_devices())

    @callback
    def websocket_handle_player(hass: HomeAssistant, connection, msg) -> None:
        @async_wrap
        def get_player() -> None:
            """Handle to get player."""
            account = msg.get("account", None)
            _LOGGER.debug("websocket_handle_player msg: %s", msg)
            client = sc_controller.get_spotify_client(account)
            resp = client._get("me/player")  # pylint: disable=W0212  # noqa: SLF001
            connection.send_message(websocket_api.result_message(msg["id"], resp))

        hass.async_add_job(get_player())

    @callback
    def websocket_handle_accounts(hass: HomeAssistant, connection, msg) -> None:
        """Handle to get accounts."""
        _LOGGER.debug("websocket_handle_accounts msg: %s", msg)
        resp = list(accounts.keys()) if accounts is not None else []
        resp.append("default")
        connection.send_message(websocket_api.result_message(msg["id"], resp))

    @callback
    def websocket_handle_castdevices(hass: HomeAssistant, connection, msg) -> None:
        """Handle to get cast devices for debug purposes."""
        _LOGGER.debug("websocket_handle_castdevices msg: %s", msg)

        known_devices = get_cast_devices(hass)
        _LOGGER.debug("%s", known_devices)
        resp = [
            {
                "uuid": str(cast_info.cast_info.uuid),
                "model_name": cast_info.cast_info.model_name,
                "friendly_name": cast_info.cast_info.friendly_name,
            }
            for cast_info in known_devices
        ]

        connection.send_message(websocket_api.result_message(msg["id"], resp))

    def start_casting(call: ServiceCall) -> None:  # noqa: PLR0912
        """Service called."""
        uri = call.data.get(CONF_SPOTIFY_URI)
        category = call.data.get(CONF_SPOTIFY_CATEGORY)
        country = call.data.get(CONF_SPOTIFY_COUNTRY)
        limit = call.data.get(CONF_SPOTIFY_LIMIT)
        search = call.data.get(CONF_SPOTIFY_SEARCH)
        random_song = call.data.get(CONF_RANDOM, False)
        repeat = call.data.get(CONF_REPEAT, False)
        shuffle = call.data.get(CONF_SHUFFLE, False)
        start_volume = call.data.get(CONF_START_VOL)
        spotify_device_id = call.data.get(CONF_SPOTIFY_DEVICE_ID)
        position = call.data.get(CONF_OFFSET)
        force_playback = call.data.get(CONF_FORCE_PLAYBACK)
        account = call.data.get(CONF_SPOTIFY_ACCOUNT)
        ignore_fully_played = call.data.get(CONF_IGNORE_FULLY_PLAYED)
        device_name = call.data.get(CONF_DEVICE_NAME)
        entity_id = call.data.get(CONF_ENTITY_ID)

        # if no market information try to get global setting
        if is_empty_str(country):
            try:
                country = config[DOMAIN][CONF_SPOTIFY_COUNTRY]
            except KeyError:
                country = None

        client = sc_controller.get_spotify_client(account)

        # verify the uri provided and clean-up if required
        if not is_empty_str(uri):

            # remove ? from badly formatted URI
            uri = uri.split("?")[0]

            if not is_valid_uri(uri):
                _LOGGER.error("Invalid URI provided, aborting casting")
                return

            # force first two elements of uri to lowercase
            uri = uri.split(":")
            uri[0] = uri[0].lower()
            uri[1] = uri[1].lower()
            uri = ':'.join(uri)

        # first, rely on spotify id given in config otherwise get one
        if not spotify_device_id:
            spotify_device_id = sc_controller.get_spotify_device_id(
                account, spotify_device_id, device_name, entity_id
            )

        if is_empty_str(uri) and is_empty_str(search) and is_empty_str(category):
            _LOGGER.debug("Transferring playback")
            current_playback = client.current_playback()
            if current_playback is not None:
                _LOGGER.debug("Current_playback from spotify: %s", current_playback)
                force_playback = True
            _LOGGER.debug("Force playback: %s", force_playback)
            client.transfer_playback(
                device_id=spotify_device_id, force_play=force_playback
            )
        elif category:
            uri = get_random_playlist_from_category(client, category, country, limit)

            if uri is None:
                _LOGGER.error("No playlist returned. Stop service call")
                return

            sc_controller.play(
                client,
                spotify_device_id,
                uri,
                random_song,
                position,
                ignore_fully_played,
            )
        else:

            if is_empty_str(uri):
                # get uri from search request
                uri = get_search_results(search, client, country)

            sc_controller.play(
                client,
                spotify_device_id,
                uri,
                random_song,
                position,
                ignore_fully_played,
            )

        if start_volume <= 100:
            _LOGGER.debug("Setting volume to %d", start_volume)
            time.sleep(2)
            client.volume(volume_percent=start_volume, device_id=spotify_device_id)
        if shuffle:
            _LOGGER.debug("Turning shuffle on")
            time.sleep(3)
            client.shuffle(state=shuffle, device_id=spotify_device_id)
        if repeat:
            _LOGGER.debug("Turning repeat on")
            time.sleep(3)
            client.repeat(state=repeat, device_id=spotify_device_id)

    # Register websocket and service
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SPOTCAST_PLAYLISTS, websocket_handle_playlists, SCHEMA_PLAYLISTS
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SPOTCAST_DEVICES, websocket_handle_devices, SCHEMA_WS_DEVICES
    )
    hass.components.websocket_api.async_register_command(
        WS_TYPE_SPOTCAST_PLAYER, websocket_handle_player, SCHEMA_WS_PLAYER
    )

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SPOTCAST_ACCOUNTS, websocket_handle_accounts, SCHEMA_WS_ACCOUNTS
    )

    hass.components.websocket_api.async_register_command(
        WS_TYPE_SPOTCAST_CASTDEVICES,
        websocket_handle_castdevices,
        SCHEMA_WS_CASTDEVICES,
    )

    hass.services.register(
        DOMAIN, "start", start_casting, schema=SERVICE_START_COMMAND_SCHEMA
    )

    return True
