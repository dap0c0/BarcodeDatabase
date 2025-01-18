import pymongo
import json

# connect to your Atlas cluster
client = pymongo.MongoClient("mongodb+srv://cadizd:3NkC4rGgaKedufa0@cluster0.2ighc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

# get the database and collection on which to run the operation
collection = client['barcodes']['test']

# Get all dictionaries from our test data file
with open("test_data.json", "r") as rfile:
    data_dict = json.load(rfile)
    data_list = []

    for key_val_pair in data_dict.items():
        _, item = key_val_pair
        data_list.append(item)

    assert len(data_list) != 0
    print(f"Inserting {len(data_list)} items to {collection}")
    collection.insert_many(data_list)
    print(f"Done!")
