import asyncio

from pymongo import AsyncMongoClient
client = AsyncMongoClient("mongodb+srv://cadizd:3NkC4rGgaKedufa0@cluster0.2ighc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

async def main():
    # Select the collection
    collection = client.test_async.tests

    # Write to the collection
    post = {
        "message": "insert one success!"
    }
    await collection.insert_one(post)

asyncio.run(main())
