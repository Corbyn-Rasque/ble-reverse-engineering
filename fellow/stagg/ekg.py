#! python3
from asyncio import Queue, Event, create_task

from fellow.stagg.state      import State
from fellow.stagg.connection import Connection
from fellow.stagg.parser     import Parser

import logging
log = logging.getLogger(__name__)

NAME            = 'FELLOW'
CHARACTERISTIC  = '00002a80-0000-1000-8000-00805f9b34fb'
PASSWORD        = b'\xef\xdd\x0b' + b'012345678901234' + b'\x9am'

class Kettle:
    state:      State
    connection: Connection
    parser:     Parser
    queue:      Queue
    event:      Event

    def __init__(self):
        self.state      = State()
        self.connection = Connection()
        self.parser     = Parser(self.state)
        self.queue      = Queue()
        self.event      = Event()

    async def scan(self) -> dict[str, str]:
        return { device.name: device.address for device in await self.connection.scan(NAME) 
                if device.name is not None }

    async def connect(self, address: str):
        async def on_notify(_, message: bytearray):
            self.queue.put_nowait(message)
            self.event.set()

        try:
            await self.connection.connect(address)
            await self.connection.subscribe(CHARACTERISTIC, on_notify)
            await self.connection.write(CHARACTERISTIC, PASSWORD)
            create_task(self.run())
        except Exception as e:
            log.error("Could not connect to %s: %s", address, e)

    async def run(self):
        while True:
            data = await self.queue.get()
            self.parser.parse(data)