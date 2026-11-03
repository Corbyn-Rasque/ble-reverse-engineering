from collections import defaultdict
from enum import IntEnum
from typing import TypeAlias, Callable, Self, overload
from dataclasses import dataclass, field

Seconds: TypeAlias = int
Degrees: TypeAlias = int

class Switch (IntEnum):
    OFF = 0x00
    ON  = 0x01

class Unit (IntEnum):
    CELSIUS     = 0x00
    FAHRENHEIT  = 0x01

type Callback[T] = Callable[[T | None, T | None], None]

class Observable[T]:
    def __init__(self, default: T | None = None):
        self.default = default

    def __set_name__(self, owner, name):
        self.name    = name
        self.private = f'_{name}'

    @overload
    def __get__(self, obj: None, objtype: type) -> Self: ...
    @overload
    def __get__(self, obj: object, objtype: type) -> T | None: ...
    def __get__(self, obj, objtype = None) -> T | None | Self:
        if obj is None:
            return self
        return getattr(obj, self.private, self.default)

    def __set__(self, obj, value: T | None):
        old = getattr(obj, self.private, self.default)
        setattr(obj, self.private, value)
        if cbs := obj.callbacks.get(self.name):
            for fn in cbs:
                fn(old, value)

class State:
    '''
    The source of truth for current kettle state. Each value is updated on a rolling basis, one after another, by the kettle.
    The values update approximately once per second, except for `unit` which updates with both `current` and `target`.

    :power:     Whether the kettle is ON or OFF
    :hold:      Whether hold mode is ON or OFF
    :mode:      ...
    :docked:    Whether the kettle is ON the base or OFF the base.
    :current:   The current temperature in degrees (integer, see `unit` for units).
    :target:    The target temperature the kettle is heating to (integer, see `unit` for units).
    :unit:      CELCIUS or FAHRENHEIT; updates with both `current` and `target`
    :timer:     Value remaining in seconds (integer) of the timer set by the kettle.
    :sequence:  The current sequence number used in commands sent.
    '''
    power   = Observable[Switch](None)
    hold    = Observable[Switch](None)
    heated  = Observable[Switch](None)
    docked  = Observable[Switch](None)
    current = Observable[Degrees](None)
    target  = Observable[Degrees](None)
    unit    = Observable[Unit](None)
    timer   = Observable[Seconds](0)

    def __init__(self):
        self.callbacks: dict        = defaultdict(list)
        self.sequence:  bytearray   = bytearray([0])

    def on(self, field: Observable, fn: Callback) -> None:
        self.callbacks[field.name].append(fn)

    def off(self, field: Observable, fn: Callback) -> None:
        self.callbacks[field.name].remove(fn)

    def __str__(self) -> str:
        return ' | '.join([
            'Power: '   + getattr(self.power,   'name', ''),
            'Hold: '    + getattr(self.hold,    'name', ''),
            'Mode: '    + getattr(self.heated,    'name', ''),
            'Docked: '  + getattr(self.docked,  'name', ''),
            'Current Temp: '    + f'{self.current}°{'F' if self.unit else 'C'}',
            'Target Temp: '     + f'{self.target}°{'F' if self.unit else 'C'}',
            'Timer: '   + f'{self.timer} Seconds'
        ])