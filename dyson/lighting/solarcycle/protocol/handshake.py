from dyson.bluetooth.collector      import Collector
from dyson.lighting.solarcycle.protocol.authorization  import Authenticate, State, ProtocolStateError
from dyson.lighting.solarcycle.protocol.messages.reauthentication import Key, Challenge, Response

class Handshake:
    def __init__(self, guid: bytes, ltk: bytes):
        self.guid = guid
        self.auth = Authenticate(ltk)

    def start(self) -> list[bytes]:
        payload = self.auth.encrypted_key()
        self.collector = Collector(Challenge.length)
        return Key.encode(self.guid + b"\x00\x00" + bytes(payload))

    def on_notify(self, chunk: bytes) -> list[bytes] | None:
        match self.auth.state:
            case State.SENT_ENCRYPTED_KEY:
                raw = self.collector.feed(chunk)
                if raw is None:
                    return None
                payload   = Challenge.decode(raw)
                challenge = self.auth.challenge_decryption(payload)
                response  = self.auth.challenge_response(challenge)
                return Response.encode(bytes(response))
            case other:
                raise ProtocolStateError("on_notify", State.SENT_ENCRYPTED_KEY, other)