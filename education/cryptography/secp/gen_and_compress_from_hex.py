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