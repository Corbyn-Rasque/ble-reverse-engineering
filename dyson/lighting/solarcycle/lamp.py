from __future__ import annotations

from asyncio import Queue, Event

from dyson.product import Dyson, Account
from dyson.bluetooth.connection import Connection
from dyson.lighting.solarcycle.state import State

from dyson.lighting.solarcycle.protocol.handshake import Handshake as AuthHandshake

from dyson.lighting.solarcycle.protocol.data import Data as Protocol
from dyson.lighting.solarcycle.protocol.services import Handshake, Data as Services
from dyson.lighting.types import Switch

import logging
log = logging.getLogger(__name__)

class Lamp(Dyson):
    state:      State
    connection: Connection
    protocol:   Protocol
    queue:      Queue[bytes]
    event:      Event

    def __init__(self, account: Account):
        self.account    = account
        self.state      = State()
        self.connection = Connection()
        self.protocol   = Protocol()
        self.queue      = Queue()
        self.event      = Event()

    async def connect(self, device) -> None:
        async def on_notify(sender, message: bytearray) -> None:
            msg = bytes(message)
            log.debug("RX from %s: %s", sender, msg.hex())
            self.queue.put_nowait(msg)
            self.event.set()

        await self.connection.connect(device)

        # During debugging, subscribe to both session characteristics.
        await self.connection.subscribe(
            "2DD10011-1C37-452D-8979-D1B4A787D0A4",
            on_notify,
        )

        await self.connection.subscribe(
            "2DD10013-1C37-452D-8979-D1B4A787D0A4",
            on_notify,
        )

        await self.handshake()

    async def handshake(self) -> None:
        # Step 1: request lamp identity.
        await self.connection.write(Handshake.Characteristic.WRITE, b"\x80\x0A")

        while True:
            message = await self.queue.get()
            log.debug("RX: %s", message.hex())

            if message.startswith(b"\x80\x0B"):
                log.debug("Identity: %s", message.hex())
                break

            log.debug("Ignoring non-identity packet: %s", message.hex())

        # Step 2: start encrypted LTK re-authentication.
        auth = AuthHandshake(self.account.guid, self.account.ltk)

        for frame in auth.start():
            log.debug("TX: %s", message.hex())
            await self.connection.write(Handshake.Characteristic.WRITE, frame)
            # await asyncio.sleep(0.03)

        # Step 3: receive challenge, send response, wait for authorization.
        while not self.state.authenticated:
            message = await self.queue.get()
            log.debug("RX: %s", message.hex())

            if len(message) == 1:
                log.debug("Ignoring status byte: %s", message.hex())
                continue

            if message.startswith(b"\x80\x26"):
                auth.auth.connection_established()
                self.state.authenticated = True
                log.debug("Authenticated")
                return

            try:
                response = auth.on_notify(message)
            except Exception as exc:
                log.debug("Ignoring packet during auth: %s (%s)", message.hex(), exc)
                continue

            if response is None:
                continue

            for frame in response:
                log.debug("TX: %s", message.hex())
                await self.connection.write(Handshake.Characteristic.WRITE, frame)

    async def power(self, on: bool):
        value = Switch.ON if on else Switch.OFF

        for frame in self.protocol.write(
            Services.Characteristic.POWER,
            value,
        ):
            await self.connection.write(
                Services.Characteristic.POWER,
                frame,
            )

    async def brightness(self, percent: int):
        for frame in self.protocol.write(
            Services.Characteristic.BRIGHTNESS,
            percent,
        ):
            await self.connection.write(
                Services.Characteristic.BRIGHTNESS,
                frame,
            )

    async def temperature(self, kelvin: int):
        for frame in self.protocol.write(
            Services.Characteristic.TEMPERATURE,
            kelvin,
        ):
            await self.connection.write(
                Services.Characteristic.TEMPERATURE,
                frame,
            )

    async def automatic(self, enabled: bool):
        value = Switch.ON if enabled else Switch.OFF

        for frame in self.protocol.write(
            Services.Characteristic.AUTOMATIC,
            value,
        ):
            await self.connection.write(
                Services.Characteristic.AUTOMATIC,
                frame,
            )

    async def motion(self, enabled: bool):
        value = Switch.ON if enabled else Switch.OFF

        for frame in self.protocol.write(
            Services.Characteristic.MOTION,
            value,
        ):
            await self.connection.write(
                Services.Characteristic.MOTION,
                frame,
            )