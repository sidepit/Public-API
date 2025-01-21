from ecdsa import SigningKey, SECP256k1
import hashlib

# In ecdsa, the private key is called signing key, and the public, verifying key.

# Specify the SECP256k1 curve; ecdsa uses NIST192p by default.
sk = SigningKey.generate(curve=SECP256k1)
vk = sk.verifying_key

signature = sk.sign(b"message")
verify = vk.verify(signature, b"message")

# Hash a message using hashlib
message = b"Hello, ECDSA!"
hashed_message = hashlib.sha256(message).digest()