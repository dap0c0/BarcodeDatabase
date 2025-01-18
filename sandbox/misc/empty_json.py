filename = "empty_filename.txt"

with open(filename, "r+") as rwfile:
    import json
    values = json.load(rwfile)
    print(values)
    print(f"Class of values {values.__class__}")
