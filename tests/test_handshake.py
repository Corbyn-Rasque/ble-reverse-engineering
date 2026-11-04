"""End-to-end tests of the LTK reauthentication handshake against a simulated lamp.

The fake lamp below plays the lamp's side of the protocol with the same key
derivation and payload format, so these tests exercise the full exchange
without any hardware.
"""

import hashlib
import hmac
import os

import pytest

from dyson.lighting.solarcycle.protocol.authorization import (
    CHALLENGE,
    NONCE,
    Authenticate,
    AuthenticationError,
    ChallengeMismatchError,
    Payload,
    ProtocolStateError,
    State,
    decrypt,
    hkdf,
)

LTK = bytes(range(16))


class FakeLamp:
    """The lamp's side of the handshake."""

    def __init__(self, ltk: bytes = LTK):
        self.key = hkdf(ltk)
        self.challenge = os.urandom(CHALLENGE)

    def open(self, payload: Payload) -> bytes:
        expected = hmac.new(self.key, payload.ciphertext, hashlib.sha256).digest()
        assert hmac.compare_digest(expected, payload.mac), "client sent a bad MAC"
        return decrypt(self.key, payload.iv, payload.ciphertext)

    def answer(self, wire: bytes, echo: bytes | None = None) -> bytes:
        """Receive the client's encrypted nonce; reply with nonce + our challenge."""
        nonce = self.open(Payload.unpack(wire))
        return bytes(Payload.build(self.key, (echo or nonce) + self.challenge))

    def verify(self, wire: bytes) -> bool:
        return self.open(Payload.unpack(wire)) == self.challenge


def test_full_handshake_succeeds():
    client, lamp = Authenticate(LTK), FakeLamp()

    reply = lamp.answer(bytes(client.encrypted_key()))
    challenge = client.challenge_decryption(Payload.unpack(reply))
    assert challenge == lamp.challenge

    assert lamp.verify(bytes(client.challenge_response(challenge)))
    client.connection_established()
    assert client.state is State.AUTHORIZED


def test_payload_survives_the_wire_format():
    payload = Payload.build(hkdf(LTK), os.urandom(32))
    restored = Payload.unpack(bytes(payload))

    assert (restored.iv, restored.ciphertext, restored.mac) == (payload.iv, payload.ciphertext, payload.mac)


def test_each_payload_uses_a_fresh_iv():
    key = hkdf(LTK)
    assert Payload.build(key, bytes(16)).iv != Payload.build(key, bytes(16)).iv


def test_tampered_reply_is_rejected_before_decryption():
    client, lamp = Authenticate(LTK), FakeLamp()
    reply = bytearray(lamp.answer(bytes(client.encrypted_key())))
    reply[NONCE] ^= 0x01  # flip one ciphertext bit

    with pytest.raises(AuthenticationError, match="MAC"):
        client.challenge_decryption(Payload.unpack(bytes(reply)))


def test_lamp_with_a_different_key_is_rejected():
    client = Authenticate(LTK)
    impostor = FakeLamp(ltk=bytes(16))
    impostor_reply = bytes(Payload.build(impostor.key, os.urandom(NONCE) + impostor.challenge))

    with pytest.raises(AuthenticationError):
        client.challenge_decryption(Payload.unpack(impostor_reply))


def test_reply_must_echo_our_nonce():
    client, lamp = Authenticate(LTK), FakeLamp()
    reply = lamp.answer(bytes(client.encrypted_key()), echo=os.urandom(NONCE))

    with pytest.raises(ChallengeMismatchError):
        client.challenge_decryption(Payload.unpack(reply))


def test_steps_must_happen_in_order():
    client = Authenticate(LTK)

    with pytest.raises(ProtocolStateError):
        client.challenge_response(os.urandom(CHALLENGE))
    with pytest.raises(ProtocolStateError):
        client.connection_established()

    client.encrypted_key()
    with pytest.raises(ProtocolStateError):
        client.encrypted_key()


def test_short_payload_is_rejected():
    with pytest.raises(ValueError, match="too short"):
        Payload.unpack(bytes(10))