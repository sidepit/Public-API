# Sidepit Cryptography Tutorial - ECDSA

## Overview

### What is ECDSA?

Elliptic Curve Digital Signature Algorithm (ECDSA) is a cryptographic algorithm for
**signing** and **verifying** digital signatures. It uses **elliptic curve cryptography** 
(ECC), which provides strong security with smaller key sizes. ECDSA cannot work with 
RSA as they are based on different cryptographic methods. It is widely used in cryptocurrency 
and is the standard for **Bitcoin** (using the secp256k1 curve).

### Common uses

- Crypto (e.g., Bitcoin for signing transactions).
- Digital certificates (SSL/TLS for secure websites).
- SSH key authentication.
- Email signing.


### Why ECDSA is used in blockchain

- Small key sizes are critical for blockchain, which requires high-speed processing.

### Comparison to RSA

- RSA uses much longer keys; ECDSA is equally secure with much smaller keys.
- ECDSA is faster in key generation, signing, and verifying.
- ECDSA uses elliptic curves (harder to break); RSA relies on the difficulty of factoring large numbers.
- ECDSA is used in cryptocurrencies; RSA is more commonly used for SSL/TLS.

## Code Examples

*Navigate into the `ecdsa` folder and run `ecdsa_example.py`*

The file below demonstrates how to:
- Generate private-public keys.
- Create and sign a message.
- Verify a signature.
- Hash a message.

```python
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
```

### Best practices for managing ECDSA keys

**If compromised, an attacker can impersonate the owner.**

- Keep the private key secure.
- Rotate keys periodically.
- Always encrypt and securely store backups of the private key.

For more info on ECDSA, please visit the [Python ECDSA documentation](https://ecdsa.readthedocs.io/en/latest/quickstart.html).