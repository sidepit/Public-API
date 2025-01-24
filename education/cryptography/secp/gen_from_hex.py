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