import asyncio
import random
class Task():
    def __init__(self,
                 id: int):
        self.id = id

    def __repr__(self):
        return str(self.id)

async def print_tasks(tasks: list):
    for task in tasks:
        await asyncio.sleep(1)
        print(task)

async def main():
    tasks = [Task(random.randint(0, i)) for i in range(10000)]
    await print_tasks(tasks)

asyncio.run(main())
