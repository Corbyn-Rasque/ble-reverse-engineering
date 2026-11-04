#! python3

from __future__ import annotations
import asyncio
from enum import IntEnum
from bleak import BleakClient, BleakScanner

class Command:
    class Heartbeat:
        COMMAND = bytearray(b'\x00')

    class Tare:
        COMMAND = bytearray(b'\x04')

    class Timer:
        COMMAND = bytearray(b'\x0d')

    HEADER      = bytearray(b'\xef\xdd')
    command:    bytearray
    



class Scale:
    COMMAND = '49535343-8841-43f4-a8d4-ecbe34729bb3'
    NOTIFY = '49535343-1e4d-4bd9-ba61-23c647249616'
    PASSWORD = b'\xef\xdd\x0b' + b'012345678901234' + b'\x9am'

    client: BleakClient | None

    weight:     float
    battery:    int

    def __init__(self):
        self.client = None