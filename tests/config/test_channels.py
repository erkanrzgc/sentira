"""Frozen channel frame: canonical, counter-free and dated."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sentira.config.channels import ChannelFrame, load_channel_frame

FRAME = Path(__file__).resolve().parents[2] / "examples/synthetic-channels.toml"


def test_shipped_frame_validates_in_canonical_order():
    frame = load_channel_frame(FRAME)
    ids = [channel.id for channel in frame.channels]
    assert ids == sorted(ids) and len(ids) == 24
    late = datetime(2029, 12, 10, tzinfo=UTC)
    assert len(frame.candidates("institution", as_of=late)) == 5
    assert len(frame.candidates("institution", as_of=datetime(2029, 12, 1, tzinfo=UTC))) == 4


def test_file_order_does_not_change_the_digest(tmp_path):
    text = FRAME.read_text(encoding="utf-8")
    head, _, rest = text.partition("[[channels]]")
    blocks = ["[[channels]]" + block for block in rest.split("[[channels]]")]
    path = tmp_path / "channels.toml"
    path.write_text(head + "".join(reversed(blocks)), encoding="utf-8")
    assert load_channel_frame(path).sha256 == load_channel_frame(FRAME).sha256
    # Direct construction must already be canonical.
    frame = load_channel_frame(FRAME)
    with pytest.raises(ValueError):
        ChannelFrame(frame.mode, frame.version, frame.channels[::-1])


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('id = "synthetic-party-03"', 'id = "synthetic-party-02"'),
        ('channel_type = "party"\nadded_at', 'channel_type = "party"\nsubscribers = 9\nadded_at'),
        ("added_at = 2029-11-01T00:00:00Z", "added_at = 2029-11-01T00:00:00"),
        ('id = "synthetic-party-03"', 'id = "Synthetic Party"'),
        ('mode = "synthetic"', 'mode = "live"'),
    ],
)
def test_invalid_frames_are_refused(tmp_path, old, new):
    text = FRAME.read_text(encoding="utf-8")
    assert old in text
    path = tmp_path / "channels.toml"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(ValueError):
        load_channel_frame(path)
