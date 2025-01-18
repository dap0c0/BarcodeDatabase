import pyscrypt

with pyscrypt.ScryptFile(b"foo", b"foo_pass", N=2048, r=8, p=1) as f:
    f.write(f"Hello World")

