import pyscrypt
import secrets
import os

class ScryptPasswordDB():
    MAX_USERS = 10
    MIN_PASSWORD_SIZE = 12
    MAX_PASSWORD_SIZE = 50
    DEFAULT_DIRECTORY_PATH = "./pass/"
    DELIMITER = "$"
    RW_OWNER_ONLY = 600
    FILE_POSTFIX = ".scrypt"
    DEFAULT_DK_LENGTH = 32

    def __init__(self,
                 min_password_size: int=MIN_PASSWORD_SIZE,
                 max_password_size: int=MAX_PASSWORD_SIZE,
                 max_users: int=MAX_USERS,
                 dir_name: str=DEFAULT_DIRECTORY_PATH
                 ):
        self._min_password_size = min_password_size
        self._max_password_size = max_password_size
        self._max_users = max_users
        self._dir_name = dir_name

        # Check whether the directory exists
        if not os.path.exists(self._dir_name):
            os.mkdir(self._dir_name, mode=600)

    def write_pass_file(self,
                        salt_generator,
                        username: str,
                        password: bytes,
                        N: int=2048,
                        r: int=8,
                        p: int=1
                        ):
        ''' Create a pass file with /<DEFAULT_DIRECTORY_PATH>/<username>.<FILE_PO<FILE_POSTFIX>
        as the file path.

        Utilize the inputted parameters N, r, p, dkLen for hash
        generation.

        Write a single line into the file as following:
        <N>$<r>$<p>$<salt>$<hash>'''
        file_path = self._dir_name + username + ScryptPasswordDB.FILE_POSTFIX

        # Generate hash with salt, then write
        # all details to the file.
        with open(file_path, "w") as wfile:
            salt = salt_generator(64).encode("utf-8")
            hash = pyscrypt.hash(password, salt, N, r, p, ScryptPasswordDB.DEFAULT_DK_LENGTH).hex()
            values = (str(N), str(r), str(p), salt.decode("utf-8"), str(hash))
            delimiter = ScryptPasswordDB.DELIMITER
            line = delimiter.join(values)
            line = line + "\n"
            wfile.write(line)

        print(f"Wrote to file {file_path}")

    def gen_random_salt(self, num_bytes: int=16) -> str:
        return secrets.token_hex(num_bytes)

    def verify_pass_file(self,
                    username: str,
                    password: bytes
                    ) -> bool:
        ''' Verify that the password entered matches the
        hash that exists for the given username.'''
        N, r, p, salt, hash = self._get_pass_params(username)

        # Recompute the hash and compare
        hash_new_bytes = pyscrypt.hash(password, salt.encode("utf-8"), N, r, p, ScryptPasswordDB.DEFAULT_DK_LENGTH)
        hash_old_bytes = bytes.fromhex(hash)
        
        print(f"OLD: {hash_old_bytes}")
        print(f"NEW: {hash_new_bytes}")
        return hash_old_bytes == hash_new_bytes

    def _get_pass_path(self, username: str):
        return self._dir_name + username + self.FILE_POSTFIX

    def _get_pass_params(self,
                         username: str
                         ) -> tuple:
        ''' Return (<N>, <r>, <p>, <salt>, <hash>)
        from the file <username>.'''
        with open(self._get_pass_path(username),  "r") as rfile:
            N, r, p, salt, hash = rfile.read().split(ScryptPasswordDB.DELIMITER)
            
        return (int(N), int(r), int(p), salt, hash)
