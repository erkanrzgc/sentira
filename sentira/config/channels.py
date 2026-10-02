"""Strict TOML input for a frozen channel frame (BACKTEST C, the channel list).

The frame is the list a seeded selection draws from. Each channel carries its
type and the time it was added, so that a channel added after a registration can
never be part of that registration's sample. No field can hold a counter.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sentira.core.document import utc
from sentira.core.registration import digest, exact, slug

MAX_CHANNELS = 10_000


@dataclass(frozen=True, slots=True)
class Channel:
    id: str
    channel_type: str
    added_at: datetime

    def __post_init__(self):
        slug(self.id)
        slug(self.channel_type)
        object.__setattr__(self, "added_at", utc(self.added_at))


@dataclass(frozen=True, slots=True)
class ChannelFrame:
    mode: str
    version: str
    channels: tuple[Channel, ...]

    def __post_init__(self):
        if self.mode != "synthetic":
            raise ValueError("Only synthetic channel frames are supported")
        slug(self.version)
        channels = self.channels
        if type(channels) is not tuple or not 0 < len(channels) <= MAX_CHANNELS:
            raise ValueError("A bounded, non-empty tuple of channels is required")
        if any(type(channel) is not Channel for channel in channels):
            raise ValueError("Validated channels are required")
        ids = [channel.id for channel in channels]
        # One canonical order, so the digest does not depend on file order.
        if ids != sorted(set(ids)):
            raise ValueError("Channel identifiers must be unique and sorted")

    @classmethod
    def from_mapping(cls, raw):
        exact(raw, ("mode", "version", "channels"))
        if not isinstance(raw["channels"], list):
            raise ValueError("Channels must be a list")
        channels = [
            Channel(**exact(item, ("id", "channel_type", "added_at"))) for item in raw["channels"]
        ]
        return cls(
            mode=raw["mode"],
            version=raw["version"],
            channels=tuple(sorted(channels, key=lambda channel: channel.id)),
        )

    @property
    def sha256(self):
        return digest(self)

    def candidates(self, channel_type, *, as_of):
        """Identifiers of one type that were in the frame at `as_of`, in order."""
        moment = utc(as_of)
        return tuple(
            channel.id
            for channel in self.channels
            if channel.channel_type == channel_type and channel.added_at <= moment
        )


def load_channel_frame(path):
    with Path(path).open("rb") as stream:
        return ChannelFrame.from_mapping(tomllib.load(stream))
