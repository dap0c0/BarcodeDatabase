import pymongo

# connect to your Atlas cluster
client = pymongo.MongoClient("mongodb+srv://cadizd:3NkC4rGgaKedufa0@cluster0.2ighc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# get the database and collection on which to run the operation
collection = client['test_new_file']['people']

# create new documents
peopleDocuments = [
    {
      "name": {
            "first": "Derek",
            "last": "Cadiz"
        },
        "age": 20
    }
]

# insert documents
collection.insert_many(peopleDocuments)

# find documents 
result = collection.find_one({ "name.last": "Cadiz" })

# print results
print("Document found:\n", result)
