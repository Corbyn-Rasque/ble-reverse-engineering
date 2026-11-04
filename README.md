# Bluetooth & Embedded Experimentation

The purpose of this repository is mainly to play around with and gain experience with Bluetooth and its protocols. I've wanted to create HomeKit devices out of my [Dyson Solarcycle Desk Lamp CD05](https://www.dyson.com/lighting/desk-lamps/solarcycle-cd05/dyson-solarcycle-desk-light-cd05-black-black) and [Fellow Stagg EKG+ Electric Kettle](https://help.acaia.co/hc/en-us/articles/360035251911--Fellow-EKG-Kettle) for some time to allow for automation, and to my knowledge no one has taken on such a project yet.

The end target of this experimentation is to create something that can run on an ESP32-C6 and interface with [HomeSpan](https://github.com/HomeSpan/HomeSpan) for the HomeKit side of things. The Python code is to accelerate experimentation with Bluetooth protocols, without the overhead of managing state machines and concurrency on an embedded device. Python should help make the protocols more obvious to implement in C++ down the line (especially for encrypted handshakes, like with the Dyson lamp).

If you'd like to experiment or join the project, you are more than welcome to!

## Where things stand

| Device | Working | In progress | Not started |
| --- | --- | --- | --- |
| Dyson Solarcycle lamp | Encrypted handshake; power, brightness, color temperature, auto mode, and motion mode commands | Reading device state (decoders written, not yet wired up) | First-time pairing handshake; ESP32 port |
| Fellow Stagg EKG+ kettle | Connecting; streaming live power, hold, current and target temperature, units, timer, and dock status | Sending commands (encoders written, not yet exposed) | ESP32 port |
| Acaia Lunar scale | | Early protocol stub (`acaia/lunar/scale.py`) | Everything else |

## Dyson

For the Dyson, you will need to find your GUID and LTK for the encrypted handshake.

There are two different kinds of handshakes: authentication and reauthentication. The former is only ever used once to set up your lamp for the first time. Every other time, reauthentication can be used. The latter is implemented here; the former is unknown.

### Getting the key

Dyson's cloud API has an endpoint that returns the LTK, but it wants an extra authorization code I haven't been able to recover. Instead, I decompiled the Android app in Android Studio, patched it to log the key, and rebuilt it. The account GUID comes from Dyson's account API, which [tool.py](dyson/tool.py) handles.

A large part of the decompilation was intended to figure out how the protocol works, which I've tried to document here and in code.

### The handshake

Both sides derive a session key from the LTK with HKDF-SHA256. Every message is encrypted with AES-CBC under a fresh random IV and authenticated with HMAC-SHA256 (encrypt-then-MAC):

1. The client sends a random nonce, encrypted.
2. The lamp sends back that nonce plus its own challenge, which proves it has the key too.
3. The client checks the MAC before decrypting anything, makes sure the nonce matches, and sends the challenge back, encrypted.
4. The lamp confirms, and the session is authorized.

The crypto lives in `dyson/lighting/solarcycle/protocol/authorization.py`, written as a state machine so the steps can't happen out of order. Message structure is in `dyson/lighting/solarcycle/protocol/messages/`.

### Framing

The lamp only takes 20 bytes per BLE write, so longer messages get split into frames. The first frame's header byte packs a frame type and the number of frames that follow, and each later frame carries its index. `dyson/bluetooth/collector.py` buffers notifications until a whole message has arrived.

## Fellow

The kettle's protocol isn't encrypted, which made it a much easier place to start (though it does need a generic password; see [ekg.py](fellow/stagg/ekg.py)). Messages start with `EF DD`, then a message type byte and a fixed-length payload. The parser reads the stream one byte at a time, so it doesn't matter how messages get split across notifications, and it skips over anything it doesn't recognize. Messages arrive over a single characteristic, cycling through nine messages sequentially (see [message.py](fellow/stagg/message.py) for details).

I figured out what each value meant by watching how the kettle behaved while changing settings one-by-one, then double-checked against community notes found later on.

Parsed values go into an observable state object: each field is a descriptor that calls any subscribed callbacks with the old and new value whenever it changes. The idea is to eventually combine this with data from an Acaia Lunar scale and a DiFluid R2 Extract to track pour-over extraction without the manual data entry. From what I've researched, the Lunar has a very similar protocol spec to the EKG+.

## Setup

Requires Python 3.12 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[examples,dev]"
```

For the lamp, copy `.env.sample` to `.env` and fill in your GUID, LTK, and the lamp's Bluetooth name. Don't commit your `.env`.

```bash
python examples/dyson_lamp.py       # authenticate, then toggle power every second
python examples/kettle_logger.py    # log kettle temperature to OUTPUT.csv
```

## Tests

```bash
python -m pytest
```

No hardware needed. The tests cover framing and reassembly, the full Dyson handshake against a simulated lamp (including tampered, impersonated, and out-of-order messages), and the kettle parser.

*Not affiliated with or endorsed by Dyson or Fellow.*