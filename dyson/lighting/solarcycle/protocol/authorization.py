from __future__ import annotations

import os, hmac, hashlib
from typing import cast
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import HKDF
from Crypto.Hash import SHA256
from enum import Enum, auto


KEY         = 16
MAC         = 32
NONCE       = 16
CHALLENGE   = 16


class AuthenticationError (Exception):
    """Base class for all errors from the LTK re-auth handshake."""

class ProtocolStateError (AuthenticationError):
    """Raised when a handshake method is called out of order."""

    def __init__(self, method: str, expected: State, actual: State):
        self.method = method
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"{method}() called in state {actual.name}, expected {expected.name}"
        )

class ChallengeMismatchError (AuthenticationError):
    """Raised when the lamp's echoed response doesn't match the nonce."""

    def __init__(self, expected: bytes, actual: bytes):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"lamp response did not match nonce "
            f"(expected {expected.hex()}, got {actual.hex()})"
        )


def hkdf(ltk: bytes) -> bytes:
    return cast(bytes, HKDF(master  = ltk, 
                            key_len = KEY,
                            salt    = b"", 
                            hashmod = SHA256, 
                            context = b"USER_AUTH_AES\x00\x00\x00"))

def encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES CBC Encryption"""
    return AES.new(key, AES.MODE_CBC, iv).encrypt(data)

def decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    """AES CBC Decryption"""
    return AES.new(key, AES.MODE_CBC, iv).decrypt(data)

class Payload:
    iv:         bytes
    ciphertext: bytes
    mac:        bytes

    def __init__(self, iv: bytes, ciphertext: bytes, mac: bytes):
        self.iv         = iv
        self.ciphertext = ciphertext
        self.mac        = mac

    @classmethod
    def build(cls, key: bytes, plaintext: bytes) -> Payload:
        """Build an outgoing Payload: encrypt + MAC."""
        iv         = os.urandom(16)
        ciphertext = encrypt(key, iv, plaintext)
        mac        = hmac.new(key, ciphertext, hashlib.sha256).digest()
        return cls(iv, ciphertext, mac)

    @classmethod
    def unpack(cls, data: bytes) -> Payload:
        """Parse an incoming wire blob: iv(16) + ciphertext(N) + mac(32)."""
        if len(data) < NONCE + MAC:
            raise ValueError(f"payload too short: {len(data)} bytes")
        iv         = data[       : NONCE ]
        ciphertext = data[ NONCE : - MAC ]
        mac        = data[ - MAC :       ]
        return cls(iv, ciphertext, mac)

    def __bytes__(self) -> bytes:
        return self.iv + self.ciphertext + self.mac


class State (Enum):
    INIT                = auto()
    SENT_ENCRYPTED_KEY  = auto()
    RECEIVED_CHALLENGE  = auto()    # after 0x07
    CHALLENGE_RESPONSE  = auto()
    AUTHORIZED          = auto()    # after 0x26

class Authenticate:
    key:    bytes
    nonce:  bytes
    state:  State

    def __init__(self, ltk: bytes):
        self.key    = hkdf(ltk)
        self.nonce  = os.urandom(NONCE)
        self.state  = State.INIT

    def encrypted_key(self) -> Payload:
        if self.state != State.INIT:
            raise ProtocolStateError("encrypted_key", State.INIT, self.state)

        payload     = Payload.build(self.key, self.nonce)
        self.state  = State.SENT_ENCRYPTED_KEY
        return payload

    def challenge_decryption(self, payload: Payload):
        if self.state != State.SENT_ENCRYPTED_KEY:
            raise ProtocolStateError("challenge_decryption", State.SENT_ENCRYPTED_KEY, self.state)

        expected = hmac.new(self.key, payload.ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, payload.mac):
            raise AuthenticationError("MAC verification failed")

        plaintext   = decrypt(self.key, payload.iv, payload.ciphertext)
        response    = plaintext[             : NONCE ]
        challenge   = plaintext[ - CHALLENGE :       ]

        if response != self.nonce:
            raise ChallengeMismatchError(self.nonce, response)

        self.state  = State.RECEIVED_CHALLENGE
        return challenge

    def challenge_response(self, challenge):
        if self.state != State.RECEIVED_CHALLENGE:
            raise ProtocolStateError("challenge_response", State.RECEIVED_CHALLENGE, self.state)

        payload     = Payload.build(self.key, challenge)
        self.state  = State.CHALLENGE_RESPONSE
        return payload
    
    def connection_established(self) -> None:
        if self.state != State.CHALLENGE_RESPONSE:
            raise ProtocolStateError("connection_established", State.CHALLENGE_RESPONSE, self.state)
        self.state = State.AUTHORIZED