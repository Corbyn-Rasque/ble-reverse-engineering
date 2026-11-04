#! python3

from fellow.stagg.ekg import Kettle, State

import asyncio
from time import time

async def main():
    kettle = Kettle()

    output = open('OUTPUT.csv', 'w')
    output.write('time,fahrenheit')


    def log_temp(old, new) -> None:
        output.write(f'\n{time()},{new}')

    kettle.state.on(State.current, log_temp)
    kettle.state.on(State.heated, lambda old, new: print(new))

    # Connect to the first available kettle
    kettles = await kettle.scan()
    _, address = next(iter(kettles.items()))
    if address:
        await kettle.connect(address)


    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await kettle.connection.disconnect()

if __name__ == "__main__":
    asyncio.run(main())