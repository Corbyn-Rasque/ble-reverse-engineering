from enum import IntEnum

import fellow.stagg.state as state
from fellow.stagg.message import MESSAGES

class State (IntEnum):
    HEADER_1 = 0
    HEADER_2 = 1
    TYPE     = 2
    PAYLOAD  = 3

class Parser:
    parser:     State
    type:       int
    expected:   int
    payload:    bytearray
    kettle:     state.State

    def __init__(self, kettle: state.State):
        self.parser     = State.HEADER_1
        self.type       = 0
        self.expected   = 0
        self.payload    = bytearray()
        self.kettle     = kettle

    def parse(self, data: bytearray):
        for byte in data:
             match self.parser:
                case State.HEADER_1: 
                    if byte ==   0xEF:
                        self.parser     = State.HEADER_2
                case State.HEADER_2:
                    if byte ==   0xDD:
                        self.parser     = State.TYPE
                    elif byte != 0xEF: 
                        self.payload    = bytearray()
                        self.parser     = State.HEADER_1
                case State.TYPE:
                    if byte in MESSAGES:
                        self.type       = byte
                        self.expected   = MESSAGES[byte].LENGTH
                        self.payload    = bytearray()
                        self.parser     = State.PAYLOAD
                    else:
                        self.payload    = bytearray()
                        self.parser    = State.HEADER_1
                case State.PAYLOAD:
                    self.payload.append(byte)
                    if len(self.payload) >= self.expected:
                        try:
                            MESSAGES[self.type].parse(self.payload, self.kettle)
                        except (ValueError, IndexError) as e:
                            print(f"Parse error for message {self.type:#04x}: {e} (payload: {self.payload.hex()})")
                        self.parser = State.HEADER_1