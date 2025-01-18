from pymongo import AsyncMongoClient
client = AsyncMongoClient("mongodb+srv://cadizd:3NkC4rGgaKedufa0@cluster0.2ighc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# Select the database
db = client.barcodes

# Select the collection
collection = db.jan_2

print(f"{db}, {collection")
