import json

my_items = {
    "oreos party size": {
        "UPC": "0123456790",
        "ASIN": "0A1BC2D3E4F5",
        "barcode_path": "aBceF=1G14e.png"
        },
    "oreos original size": {
        "UPC": "foo",
        "ASIN": "bar",
        "barcode_path": "bruh"
        }
    }

# Dict to string
print("\nDict to string")
print(my_items.__class__)
value = json.dumps(my_items)
print(value)
print(f"Class of value: {value.__class__}")

# String to dict
print("\nString to dict.")
dict_value = json.loads(value)
print(dict_value)
print(f"Class of dict_value: {dict_value.__class__}")

# Write to file
filename = "test_filename.txt"

with open(filename, "w") as wfile:
    print(f"\nWriting to {filename}")
    json.dump(my_items, wfile, indent=4)

# Read from file
with open(filename, "r") as rfile:
    print(f"\nReading from {filename}")
    dict_read = json.load(rfile)
    print(dict_read)
    print(f"Class of dict_read: {dict_read.__class__}")

