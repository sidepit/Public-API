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