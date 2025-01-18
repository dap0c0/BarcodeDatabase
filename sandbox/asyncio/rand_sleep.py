import asyncio, random

async def rnd_sleep(t: float | int):
    # sleep for time seconds on average
    await asyncio.sleep(t * random.random() * 2)

async def producer(id: int, queue: asyncio.Queue):
    while True:
        # Produce random token and put in queue.
        token = random.random()

        if token < .05:
            break

        print(f"[Producer {id}]: produced {token}")
        await queue.put(token)
        await rnd_sleep(.1)

async def consumer(id: int, queue: asyncio.Queue):
    while True:
        token = await queue.get()
        await rnd_sleep(.3)
        queue.task_done()
        print(f"[Consumer {id}]: consumed {token}")

async def main():
    queue = asyncio.Queue()
    producers = [asyncio.create_task(producer(i, queue)) for i in range(3)]
    consumers = [asyncio.create_task(consumer(i, queue)) for i in range(10)]
    
    # wait for producers to finish
    await asyncio.gather(*producers)
    print("---- Done producing!")

    # wait until the entirety of the queue is empty!
    await queue.join()
    print("---- Done consuming!")

    for c in consumers:
        c.cancel()

asyncio.run(main())


