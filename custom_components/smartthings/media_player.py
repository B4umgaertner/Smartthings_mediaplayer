"""Support for media players through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability, Command, Attribute

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
    MediaPlayerDeviceClass
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

CONTROLLABLE_SOURCES = ["bluetooth", "wifi"]

VALUE_TO_STATE = {
    "buffering": MediaPlayerState.BUFFERING,
    "pause": MediaPlayerState.PAUSED,
    "paused": MediaPlayerState.PAUSED,
    "play": MediaPlayerState.PLAYING,
    "playing": MediaPlayerState.PLAYING,
    "stop": MediaPlayerState.IDLE,
    "stopped": MediaPlayerState.IDLE,
    "on": MediaPlayerState.ON,
    "off": MediaPlayerState.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add media players for a config entry."""
    entry_data = config_entry.runtime_data
    async_add_entities(
        [
            SmartThingsMediaPlayer(entry_data.client, entry_data.rooms, device)
            for device in entry_data.devices.values()
            if any(
                capability in device.status[MAIN]
                for capability in get_capabilities(device.status[MAIN])
            )
        ]
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
        Capability.media_playback_repeat,
        Capability.media_playback_shuffle,
        Capability.switch,
    ]
    # Must have one of these.
    media_player_capabilities = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
        Capability.media_playback_repeat,
        Capability.media_playback_shuffle,
    ]
    if any(capability in capabilities for capability in media_player_capabilities):
        return supported
    return None


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player."""

    _attr_name = None

    def __init__(self, client, rooms: dict[str, str], device) -> None:
        """Initialize the media_player class."""
        super().__init__(
            client,
            device,
            rooms,
            {
                Capability.audio_mute,
                Capability.audio_volume,
                Capability.media_input_source,
                Capability.media_playback,
                Capability.media_playback_repeat,
                Capability.media_playback_shuffle,
                Capability.switch,
            },
        )
        self._attr_supported_features = self._determine_features()

    def _determine_features(self) -> MediaPlayerEntityFeature:
        """Determine supported features based on capabilities."""
        features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
        )
        if self.supports_capability(Capability.audio_volume):
            features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.supports_capability(Capability.audio_mute):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.supports_capability(Capability.switch):
            features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        if self.supports_capability(Capability.media_input_source):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.supports_capability(Capability.media_playback_shuffle):
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self.supports_capability(Capability.media_playback_repeat):
            features |= MediaPlayerEntityFeature.REPEAT_SET
        return features

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the media player off."""
        await self.execute_device_command(Capability.switch, Command.OFF)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the media player on."""
        await self.execute_device_command(Capability.switch, Command.ON)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute volume."""
        if mute:
            await self.execute_device_command(Capability.audio_mute, Command.MUTE)
        else:
            await self.execute_device_command(Capability.audio_mute, Command.UNMUTE)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.execute_device_command(
            Capability.audio_volume,
            Command.SET_VOLUME,
            argument=int(volume * 100),
        )

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self.execute_device_command(Capability.audio_volume, Command.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self.execute_device_command(Capability.audio_volume, Command.VOLUME_DOWN)

    async def async_media_play(self) -> None:
        """Play media."""
        await self.execute_device_command(Capability.media_playback, Command.PLAY)

    async def async_media_pause(self) -> None:
        """Pause media."""
        await self.execute_device_command(Capability.media_playback, Command.PAUSE)

    async def async_media_stop(self) -> None:
        """Stop media."""
        await self.execute_device_command(Capability.media_playback, Command.STOP)

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        await self.execute_device_command(
            Capability.media_input_source,
            Command.SET_INPUT_SOURCE,
            argument=source,
        )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        await self.execute_device_command(
            Capability.media_playback_shuffle,
            Command.SET_PLAYBACK_SHUFFLE,
            argument=shuffle,
        )

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.execute_device_command(
            Capability.media_playback_repeat,
            Command.SET_PLAYBACK_REPEAT,
            argument=repeat,
        )

    @property
    def device_class(self):
        """Return the device class."""
        return MediaPlayerDeviceClass.SPEAKER

    @property
    def media_title(self):
        """Return the media title if available."""
        if (self.state in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED] and
            'trackDescription' in self._device.status.attributes):
            return self._device.status.attributes['trackDescription'].value
        return None

    @property
    def state(self) -> MediaPlayerState | None:
        """Get the current state of the media player."""
        if self.get_attribute_value(Capability.switch, Attribute.SWITCH):
            if self.source is not None and self.source in CONTROLLABLE_SOURCES:
                playback_status = self.get_attribute_value(
                    Capability.media_playback, Attribute.PLAYBACK_STATUS
                )
                if playback_status in VALUE_TO_STATE:
                    return VALUE_TO_STATE[playback_status]
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def is_volume_muted(self) -> bool | None:
        """Return if the media player is muted."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE:
            return self.get_attribute_value(Capability.audio_mute, Attribute.MUTE)
        return None

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_SET:
            volume = self.get_attribute_value(Capability.audio_volume, Attribute.VOLUME)
            if volume is not None:
                return float(volume) / 100
        return None

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self.get_attribute_value(
                Capability.media_input_source, Attribute.INPUT_SOURCE
            )
        return None

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of available input sources."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self.get_attribute_value(
                Capability.media_input_source, Attribute.SUPPORTED_INPUT_SOURCES
            )
        return None

    @property
    def shuffle(self) -> bool | None:
        """Return True if shuffle is enabled."""
        if self.supported_features & MediaPlayerEntityFeature.SHUFFLE_SET:
            return self.get_attribute_value(
                Capability.media_playback_shuffle, Attribute.PLAYBACK_SHUFFLE
            )
        return None

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if self.supported_features & MediaPlayerEntityFeature.REPEAT_SET:
            return self.get_attribute_value(
                Capability.media_playback_repeat, Attribute.PLAYBACK_REPEAT_MODE
            )
        return None
