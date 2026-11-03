from dyson.lighting.types           import Outgoing, Incoming, ENDIAN
from dyson.lighting.solarcycle.protocol.authorization  import Payload

class Key (Outgoing):
    header = b"\x06"
    length = 83

    @classmethod
    def assemble(cls, payload: bytes) -> bytes:
        return payload

class Challenge (Incoming):
    header = b"\x07"
    length = 83

    @classmethod
    def parse(cls, payload: bytes) -> Payload:
        return Payload.unpack(payload[2:])

class Response (Outgoing):
    header = b"\x08"
    length = 67

    @classmethod
    def assemble(cls, payload: bytes) -> bytes:
        return b"\x00\x00" + payload