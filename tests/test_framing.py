import pytest

from dyson.bluetooth.collector import Collector
from dyson.bluetooth.framing import DATA, LIMIT, Frames

# The header's count nibble holds 4 bits, so a message spans at most 16 frames.
MAX_MESSAGE = 16 * DATA


def message(length: int) -> bytes:
    return bytes(i % 256 for i in range(length))


@pytest.mark.parametrize("length", [0, 1, LIMIT - 1])
def test_short_messages_are_sent_unframed(length):
    assert Frames.pack(message(length)) == [message(length)]


@pytest.mark.parametrize("length", [LIMIT, LIMIT + 1, 2 * DATA, 2 * DATA + 1, 100, MAX_MESSAGE])
def test_long_messages_fit_in_ble_frames(length):
    frames = Frames.pack(message(length))

    assert all(len(frame) <= LIMIT for frame in frames)
    assert frames[0][0] >> 4 == 0x8                   # frame type nibble
    assert frames[0][0] & 0x0F == len(frames) - 1     # remaining-frame count
    assert [frame[0] for frame in frames[1:]] == list(range(1, len(frames)))


@pytest.mark.parametrize("length", [0, 1, LIMIT - 1, LIMIT, LIMIT + 1, 2 * DATA + 1, 100, MAX_MESSAGE])
def test_pack_then_unpack_round_trips(length):
    original = message(length)
    wire = b"".join(Frames.pack(original))

    assert Frames.unpack(wire) == original
    assert Frames.length(length) == len(wire)


def test_unpack_rejects_an_unexpected_frame_type():
    wire = bytearray(b"".join(Frames.pack(message(40))))
    wire[0] = (0x3 << 4) | (wire[0] & 0x0F)

    with pytest.raises(ValueError, match="frame type"):
        Frames.unpack(bytes(wire))


def test_collector_waits_for_every_frame_then_reassembles():
    original = message(70)
    frames = Frames.pack(original)
    collector = Collector(len(original))

    for frame in frames[:-1]:
        assert collector.feed(frame) is None
    assert collector.feed(frames[-1]) == original


def test_collector_resets_after_each_message():
    collector = Collector(30)
    for payload in (message(30), message(30)[::-1]):
        frames = Frames.pack(payload)
        results = [collector.feed(frame) for frame in frames]
        assert results[-1] == payload


def test_collector_rejects_extra_data():
    collector = Collector(5)
    with pytest.raises(ValueError, match="more data"):
        collector.feed(message(6))