# Sidepit Cryptography Tutorial - Secp256k1

## Overview

### What is Secp256k1?

Secp256k1 is an elliptic curve used in cryptography, particularly in Bitcoin. 
It generates public-private key pairs, enabling secure digital signatures and 
transactions. Secp256k1 is favored for its efficiency and security in blockchain 
technology. It uses points and coordinates to generate shorter keys compared to 
older methods.

### Common Uses

- crypto (bitcoin).
- digital signatures.
- crypto wallets.

### Comparison to Secp256r1

Secp256r1 is standardized by the National Institute of Standards and Technology (NIST).
In contrast, Secp256k1 is not standardized by any government body, making it favored in 
decentralized systems like cryptocurrencies. Secp256k1 has a simpler equation, making it 
more efficient for blockchain applications. Secp256r1 is commonly used in SSL, web, 
government, and enterprise applications.

## Code Examples

*Navigate into the `secp` folder and run the respective files.*

**secp/keygen_sign_verify.py**

The file below demonstrates how to:
- Generate private-public keys.
- Create and sign a message.
- Verify a signature.

```python
from secp256k1 import PrivateKey, PublicKey

privkey = PrivateKey()
# The raw private key in hexadecimal
private_key_hex = privkey.private_key 

privkey_der = privkey.serialize()
deserialized_privkey = privkey.deserialize(privkey_der)

# An ECDSA signature object 
sig = privkey.ecdsa_sign(b'hello')
# Verifies the signature is legitimate using the public key
verified = privkey.pubkey.ecdsa_verify(b'hello', sig)

sig_der = privkey.ecdsa_serialize(sig)
sig2 = privkey.ecdsa_deserialize(sig_der)

pubkey = privkey.pubkey
pub = pubkey.serialize()
# Creates a Public Key from the serialized version of the original private key.
pubkey2 = PublicKey(pub, raw=True)
```

**secp/gen_from_hex.py**

- Demonstrates how to create a private key and sign messages from hexadecimal strings, then serialize the signature.

```python
from secp256k1 import PrivateKey

key = '31a84594060e103f5a63eb742bd46cf5f5900d8406e2726dedfc61c7cf43ebad'
msg = '9e5755ec2f328cc8635a55415d0e9a09c2b6f2c9b0343c945fbbfe08247a4cbe'
sig = '30440220132382ca59240c2e14ee7ff61d90fc63276325f4cbe8169fc53ade4a407c2fc802204d86fbe3bde6975dd5a91fdc95ad6544dcdf0dab206f02224ce7e2b151bd82ab'

# Create a mutable sequence of bytes from the hexadecimal string "key"
privhex = bytearray.fromhex(key)
# Convert the mutable byte array into an immutable sequence of bytes
privbyt = bytes(privhex)
# Use raw=True to indicate we are using a raw binary format (not encoded)
privkey = PrivateKey(privbyt, raw=True)


sighex = bytearray.fromhex(msg)
sigbyt = bytes(sighex)
sig_check = privkey.ecdsa_sign(sigbyt, raw=True)

sig_ser = privkey.ecdsa_serialize(sig_check)
```

**secp/gen_and_compress_from_hex.py**

- Demonstrates how to generate a private key and serialize the public key in both compressed and uncompressed formats using hexadecimal strings.

```python
from secp256k1 import PrivateKey

key = '7ccca75d019dbae79ac4266501578684ee64eeb3c9212105f7a3bdc0ddb0f27e'
pub_compressed = '03e9a06e539d6bf5cf1ca5c41b59121fa3df07a338322405a312c67b6349a707e9'
pub_uncompressed = '04e9a06e539d6bf5cf1ca5c41b59121fa3df07a338322405a312c67b6349a707e94c181c5fe89306493dd5677143a329065606740ee58b873e01642228a09ecf9d'

privhex = bytearray.fromhex(key)
privbyt = bytes(privhex)
privkey = PrivateKey(privbyt)

pubkey_ser_comp   = privkey.pubkey.serialize()
# Serialize the public key in uncompressed format.
pubkey_ser_uncomp = privkey.pubkey.serialize(compressed=False)
```

**secp/create_wallet_address.py**

- Demonstrates how to create a legacy Bitcoin wallet address (p2k2h)

```python
from secp256k1 import PrivateKey
import hashlib
import base58

privkey = PrivateKey()
pubkey = privkey.pubkey.serialize(compressed=True)

# Hash the public key
sha256_pubkey = hashlib.sha256(pubkey).digest()

# Create a new hashing object that uses the RIPEMD-160 algorithm
ripemd160 = hashlib.new('ripemd160')
ripemd160.update(sha256_pubkey)
# Compute the RIPEMD-160 hash of the input and store the result
hashed_pubkey = ripemd160.digest()

# Add version byte in front of RIPEMD-160 hash (0x00 for Bitcoin mainnet)
versioned_hashed_pubkey = b'\x00' + hashed_pubkey

# Perform SHA-256 twice on the versioned public key
checksum = hashlib.sha256(hashlib.sha256(versioned_hashed_pubkey).digest()).digest()[:4]

# Append checksum to the versioned public key
binary_address = versioned_hashed_pubkey + checksum

# Convert to Base58 to get the wallet address
wallet_address = base58.b58encode(binary_address)

print(f"Wallet Address: {wallet_address.decode()}")
```
For more info on Secp256k1 in python, please visit the [secp256k1-py Github repo](https://github.com/ludbb/secp256k1-py).