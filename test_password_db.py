from ScryptPasswordDB import ScryptPasswordDB
db = ScryptPasswordDB()
import secrets
import time

def test_salt_generation():
    for i in range(64):
        salt = db.gen_random_salt(i)
        salt_bytes = bytearray.fromhex(salt)
        assert len(salt_bytes) == i
        print(f"Salt [{i}]: {salt}")
        
def test_write_pass_file():
    write = lambda name, password: db.write_pass_file(ScryptPasswordDB.gen_random_salt, name, bytes(password, "utf-8"), N=2048)
    display_test = lambda test_name: print(f"\n<--------- {test_name} ---------->")

    def basic_test():
        display_test("basic_test")
        write("derek", "password")

    def random_tests():
        def random_test(num_users: int):
            display_test(f"random_tests [{num_users}]")

            for _ in range(num_users):
                username = secrets.token_hex(8)
                password = secrets.token_hex(32)
                start = time.perf_counter()
                write(username, password)
                end = time.perf_counter()
                total = end - start
                print(f"Password written in {total}s")

        for i in range(1000):
            random_test(i)

    def display_all_files_written():
        display_test(f"Display all files written")
        import os
        import os.path
        dir_content = os.listdir("./pass")
        print(f"# Files: {len(dir_content)}")
        
        for item in dir_content:
            with open("./pass/" + item, "r") as rfile:
                print(f"./pass/{item}")
                print(rfile.read())

    def test_param_get():
        N, r, p, salt, hash = db._get_pass_params("derek")
        print(f"N: {N}")
        print(f"r: {r}")
        print(f"p: {p}")
        print(f"salt: {salt}")
        print(f"hash: {hash}")

    def test_hash_comparison():
        print(f"Derek, password: {db.verify_pass_file("derek", b"password")}")

    def test_hash_comparison_random(num_users: int):
        ''' Positives tests.'''
        assert isinstance(num_users, int)

        for _ in range(num_users):
            # Generate password file for user
            username = secrets.token_hex(8)
            password = secrets.token_hex(16)
            db.write_pass_file(db.gen_random_salt, username, bytes(password, "utf-8"))

            # Compare the password
            print(f"{username} password check: {db.verify_pass_file(username, bytes(password, "utf-8"))}")

    def test_hash_comparison_random_false(num_users: int):
        assert isinstance(num_users, int)

        # Generate password file for users
        for _ in range(num_users):
            # Generate password file for user
            username = secrets.token_hex(8)
            password = secrets.token_hex(16)
            db.write_pass_file(db.gen_random_salt, username, bytes(password, "utf-8"))

            # Compare the password to size 0
            print(f"{username} password check: {db.verify_pass_file(username, b"")}")
            
            # Compare the password to size 1
            print(f"{username} password check: {db.verify_pass_file(username, b"f")}")

    # basic_test()                          # passed
    # test_param_get()                      # passed
    # test_hash_comparison()                # passed
    # test_hash_comparison_random(10)       # passed
    # test_hash_comparison_random_false(10) # passed

    # random_tests()
    # display_all_files_written()

if __name__ == "__main__":
    # test_salt_generation()
    test_write_pass_file()
