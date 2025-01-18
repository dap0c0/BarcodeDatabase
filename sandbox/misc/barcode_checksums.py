import barcode
import io

codes = ["012345123450", "060383123450", "05870332608"]# last digit is 8

def generate_barcode(io, code, calculate_checksum=False):
    assert isinstance(code, str)
    UPC = barcode.get_barcode_class("upc")
    upc = UPC(code)
    options = dict(add_checksum=calculate_checksum)
    print(f"Writing {code} to {io}: checksum={calculate_checksum}")
    upc.write(io, options)

def test_without_checksum():
    streams = []
    
    for code in codes:
        stream = io.BytesIO()
        generate_barcode(stream, code, calculate_checksum=False)
        streams.append(stream)
        
    # Display the svg
    for stream in streams:
        print(f"\n\n\n--------------------------------------\n\n\n")
        print(stream.getvalue())

def test_with_checksum():
    print("\n\n<----------Testing with checksum----------->")
    streams = []
    
    for code in codes:
        stream = io.BytesIO()
        generate_barcode(stream, code, calculate_checksum=True)
        streams.append(stream)

    # Display the svg
    for stream in streams:
        print(f"\n\n\n--------------------------------------\n\n\n")
        print(stream.getvalue())

if __name__ == "__main__":
    test_without_checksum()
    test_with_checksum()
