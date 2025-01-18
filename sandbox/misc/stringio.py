from StringIO import StringIO
import time
def measure_time(fx):
    start = time.time()
    fx
    end = time.time()
    return end - start

def generate_string_io(num_ints):
    buffer = StringIO()

    for i in range(num_ints):
        buffer.write(str(i))

    result = buffer.getvalue()
    buffer.close()

def generate_string_normal(num_ints):
    result = ""
    
    for i in range(num_ints):
        result += str(i)

    return result

def test_generation(num_ints):
    print("\n# Ints: %d" % num_ints)
    print("Time of StringIO: %f" % measure_time(generate_string_io(num_ints)))
    print("Time of normal concatenation: %f" % measure_time(generate_string_normal(num_ints)))

base_ints = 10000

for i in range(4):
    test_generation(base_ints**i)
