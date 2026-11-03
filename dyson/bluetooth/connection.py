import asyncio
from enum import Enum, auto
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice

class State (Enum):
    IDLE          = auto()
    SCANNING      = auto()
    CONNECTED     = auto()
    DISCONNECTING = auto()

class Connection:
    client:     BleakClient | None
    state:      State
    scanning:   asyncio.Task | None
    timeout:    int

    def __init__(self, timeout: int = 5):
        self.client     = None
        self.state      = State.IDLE
        self.scanning   = None
        self.timeout    = timeout

    async def scan(self, name: str) -> list[BLEDevice]:
        match self.state:
            case State.SCANNING:
                if self.scanning:
                    self.scanning.cancel()
                    await asyncio.sleep(0)
            case State.IDLE:
                pass
            case _:
                return []
            
        self.state      = State.SCANNING
        self.scanning   = asyncio.current_task()
        try:
            devices     = await BleakScanner.discover()
            return [device for device in devices
                        if device.name is not None and name in device.name]
        finally:
            self.state      = State.IDLE
            self.scanning   = None

    async def connect(self, device):
        match self.state:
            case State.CONNECTED:
                return
            case State.IDLE:
                self.client = BleakClient(
                    device, 
                    disconnected_callback = self._on_disconnect, 
                    timeout = self.timeout
                )
                await self.client.connect()
                self.state  = State.CONNECTED
            case _:
                await asyncio.sleep(0.5)
                await self.connect(device)
            
    async def disconnect(self):
        match self.state:
            case State.CONNECTED:
                self.state = State.DISCONNECTING
                if self.client:
                    await self.client.disconnect()
                self.state = State.IDLE
            case _:
                return

    # async def write(self, characteristic: str, data: bytes | bytearray):
    #     if self.client and self.client.is_connected:
    #         await self.client.write_gatt_char(characteristic, data)

    async def write(self, characteristic: str, data: bytes | bytearray):
        if self.client and self.client.is_connected:
            await self.client.write_gatt_char(
                characteristic,
                data,
                response=False,
            )

    async def subscribe(self, characteristic: str, callback):
        if self.client and self.state == State.CONNECTED:
            await self.client.start_notify(characteristic, callback)

    def _on_disconnect(self, client):
        intentional = self.state == State.DISCONNECTING
        self.state  = State.IDLE
        if not intentional:
            ...