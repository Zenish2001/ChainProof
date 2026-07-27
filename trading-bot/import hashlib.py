import hashlib

ID_HEX = "ED00AF5F774E4135E7746419FEB65DE8AE17D6950C95CEC3891070FBB5B03C78"
TARGET_BYTE = 0x2F

def find_x():
    id_bytes = bytes.fromhex(ID_HEX)
    n = 0
    while True:
        if n == 0:
            x_bytes = b"\x00"
        else:
            length = (n.bit_length() + 7) // 8
            x_bytes = n.to_bytes(length, "big")
        digest = hashlib.sha256(x_bytes + id_bytes).digest()
        if TARGET_BYTE in digest:
            return x_bytes, digest
        n += 1

x_bytes, digest = find_x()
print("x =", x_bytes.hex())
print("SHA-256(x||id) =", digest.hex())