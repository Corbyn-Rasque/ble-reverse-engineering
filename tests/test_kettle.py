from fellow.stagg.parser import Parser
from fellow.stagg.state import State, Switch, Unit

HEADER = bytes([0xEF, 0xDD])

# Message types and payload lengths from fellow/stagg/message.py
POWER, HOLD, TARGET, CURRENT, TIMER, DOCKED = 0x00, 0x01, 0x02, 0x03, 0x04, 0x08


def frame(kind: int, *payload: int) -> bytes:
    return HEADER + bytes([kind, *payload])


def parse(*chunks: bytes) -> State:
    state = State()
    parser = Parser(state)
    for chunk in chunks:
        parser.parse(bytearray(chunk))
    return state


def test_parses_each_message_type():
    state = parse(
        frame(POWER, 1, 0),
        frame(HOLD, 1, 0),
        frame(TARGET, 205, Unit.FAHRENHEIT, 0, 0),
        frame(CURRENT, 180, Unit.FAHRENHEIT, 0, 0),
        frame(TIMER, 42, 0),
        frame(DOCKED, 1, 0),
    )

    assert state.power is Switch.ON
    assert state.hold is Switch.ON
    assert (state.target, state.current, state.unit) == (205, 180, Unit.FAHRENHEIT)
    assert state.timer == 42
    assert state.docked is Switch.ON


def test_messages_split_across_notifications():
    stream = frame(CURRENT, 93, Unit.CELSIUS, 0, 0) + frame(POWER, 1, 0)
    state = parse(*(stream[i : i + 1] for i in range(len(stream))))  # one byte at a time

    assert (state.current, state.unit, state.power) == (93, Unit.CELSIUS, Switch.ON)


def test_skips_noise_before_a_header():
    state = parse(bytes([0x12, 0xEF, 0x00, 0xEF]) + frame(POWER, 1, 0))
    assert state.power is Switch.ON


def test_recovers_after_an_unknown_message_type():
    # 0xFF is not a known type. The parser must go back to looking for a header,
    # not treat the next byte (0x04, the Timer type) as a message type.
    state = parse(HEADER + bytes([0xFF, TIMER]) + frame(POWER, 1, 0))

    assert state.power is Switch.ON
    assert state.timer == 0  # unchanged default


def test_observers_get_old_and_new_values():
    state = State()
    changes = []
    state.on(State.current, lambda old, new: changes.append((old, new)))

    state.current = 90
    state.current = 95

    assert changes == [(None, 90), (90, 95)]


def test_observers_can_unsubscribe():
    state = State()
    changes = []
    record = lambda old, new: changes.append(new)

    state.on(State.power, record)
    state.power = Switch.ON
    state.off(State.power, record)
    state.power = Switch.OFF

    assert changes == [Switch.ON]


def test_observers_are_per_field_and_per_instance():
    first, second = State(), State()
    seen = []
    first.on(State.target, lambda old, new: seen.append(new))

    first.current = 100
    second.target = 200
    first.target = 205

    assert seen == [205]