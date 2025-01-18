import pyscrypt
import time

salt = b"whatarandomsaltbrolol"
passwd = b"qwertypassword1234"

start = time.perf_counter()
key = pyscrypt.hash(password=passwd, salt=salt, N=2048, r=8, p=1, dkLen=32)
total = time.perf_counter() - start
print(f"Derived key in {total}s: {key.hex()}")
print(f"Derived key bytes: {key}")
print(f"Key class: {key.__class__}")
