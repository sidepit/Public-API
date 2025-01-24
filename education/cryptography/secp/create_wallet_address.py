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