import click
import bech32
from pathlib import Path
from secp256k1 import PrivateKey
from hashlib import sha256 
from ripemd.ripemd160 import ripemd160  # import function
import hashlib
import base58
import secrets
import os
from tabulate import tabulate
from rich.console import Console
from rich.table import Table
from datetime import datetime
from rich.text import Text
from rich.panel import Panel

class SidepitIDManager:
    """
    A manager for Sidepit IDs and wallet addresses.

    This class provides methods for creating, loading, and retrieving Sidepit IDs and wallet 
    addresses, using cryptographic operations to securely manage public and private keys.

    Attributes:
        WALLET_FILE_PATH (Path): Path to the file where the wallet private key is stored.
    """
    FOLDER_WALLETS_PATH = Path.home() / ".spwallets" 
    # WALLET_FILE_PATH = Path.home() / ".spwallets" / ".spwallet"

    def __init__(self) -> None:
        if not self.have_folder():
            self.create_folder()
        files = os.listdir(self.FOLDER_WALLETS_PATH) #if self.FOLDER_WALLETS_PATH.exists() else []
        self.wallet_file_path = self.FOLDER_WALLETS_PATH / files[0] if files else ""
        self.active_wallet = files[0] if files else ""
        self.watch_only_id = None  # For watch-only mode without private key

    def have_folder(self) ->bool:
        return self.FOLDER_WALLETS_PATH.exists()
    
    def create_folder(self) -> None:
        os.makedirs(self.FOLDER_WALLETS_PATH)

    def have_id(self) -> bool: 
        return bool(self.wallet_file_path) or bool(self.watch_only_id)
    
    def is_watch_only(self) -> bool:
        """Check if current ID is watch-only (no private key)"""
        return bool(self.watch_only_id) and not bool(self.wallet_file_path)
    
    def get_id(self) -> str:
        if self.watch_only_id:
            return self.watch_only_id
        self.btcaddress = self.load_sidepit_id()
        return self.btcaddress
    
    def set_watch_only_id(self, trader_id: str) -> None:
        """Set a watch-only trader ID without needing private key"""
        # Basic validation - should be a bech32 address
        if not trader_id.startswith('bc1'):
            raise ValueError("Invalid trader ID format. Should start with 'bc1'")
        self.watch_only_id = trader_id
        self.wallet_file_path = ""  # Clear wallet path for watch-only mode 

    def create_sidepit_id(self) -> None:
        privkey = PrivateKey(secrets.token_bytes(32))
        wallet_name=self.write_key(self.private_key_to_wif(privkey.serialize()))
        return wallet_name

    def write_key(self, wif): 
        # if self.wallet_file_path and self.wallet_file_path.exists():
        #     raise "wallet exists" 
        self.verify_wif(wif)
        number_of_wallets=len(os.listdir(self.FOLDER_WALLETS_PATH))
        self.wallet_file_path = self.FOLDER_WALLETS_PATH / f".spwallet{number_of_wallets}"
        with open(self.wallet_file_path, 'w') as sp_wallet:
            sp_wallet.write(wif)
        return f"wallet{number_of_wallets}"
        # self.update_active_wallet_address(f".spwallet{number_of_wallets}")

    def verify_wif(self, wif):
        PrivateKey(self.wif_to_private_key(wif), False)

    def read_wif(self) -> str:
        if self.is_watch_only():
            raise RuntimeError("Cannot access private key in watch-only mode")
        with open(self.wallet_file_path, "r") as sp_wallet:
            return sp_wallet.read()
    
    def wif(self) -> str:
        if self.is_watch_only():
            raise RuntimeError("Cannot access WIF in watch-only mode")
        return self.read_wif().strip()

    def load_sidepit_id(self) -> str:
        if self.is_watch_only():
            return self.watch_only_id
        wif_content = self.read_wif()
        pk_hex = self.wif_to_private_key(wif_content) # might need to use compressed in the future..
        return self.toSegwit0Address(pk_hex)

    def toSegwit0Address(self, private_key_hex) -> str:
        privkey = PrivateKey(bytes.fromhex(private_key_hex), raw=True)
        pubkey = privkey.pubkey.serialize()
        self.public_key = pubkey.hex()
        sha256_hash = sha256(pubkey).digest()
        ripemd160_hash = ripemd160(sha256_hash).hex()
        return bech32.encode("bc",0,bytearray.fromhex(ripemd160_hash))

    def private_key_to_wif(self, private_key_hex, compressed=True):
        # Step 1: Add version byte (0x80 for Bitcoin mainnet)
        version_byte = b'\x80'
        private_key = bytes.fromhex(private_key_hex)
        
        # Step 2: Add compression flag if required
        if compressed:
            extended_key = version_byte + private_key + b'\x01'
        else:
            extended_key = version_byte + private_key
        
        # Step 3: Perform double SHA-256 hashing
        first_sha = hashlib.sha256(extended_key).digest()
        second_sha = hashlib.sha256(first_sha).digest()
        
        # Step 4: Take the first 4 bytes of the second SHA-256 hash as the checksum
        checksum = second_sha[:4]
        
        # Step 5: Concatenate the extended key with the checksum
        final_key = extended_key + checksum
        
        # Step 6: Encode the result in Base58
        wif = base58.b58encode(final_key)
        return wif.decode('utf-8')

    def wif_to_private_key(self, wif):
        # Step 1: Decode the WIF string from Base58
        decoded = base58.b58decode(wif)
        
        # Step 2: Separate the components
        # - First byte is the version byte
        # - Last 4 bytes are the checksum
        # - The remaining bytes are the private key (and possibly a compression flag)
        checksum = decoded[-4:]
        key_with_optional_compression = decoded[1:-4]
        
        # Step 3: Calculate checksum of the decoded key and compare to the last 4 bytes
        hash1 = hashlib.sha256(decoded[:-4]).digest()
        hash2 = hashlib.sha256(hash1).digest()
        if hash2[:4] != checksum:
            raise ValueError("Invalid WIF checksum")
        
        # Step 4: Determine if the private key is compressed by checking the last byte
        if key_with_optional_compression[-1] == 0x01:
            # Remove the compression byte to get the raw private key
            private_key = key_with_optional_compression[:-1]
            compressed = True
        else:
            private_key = key_with_optional_compression
            compressed = False
        
        # Step 5: Convert the private key to hexadecimal format
        private_key_hex = private_key.hex()
        
        return private_key_hex
    
    def import_wif(self, wif: str) -> None:
        try:
            wallet_name=self.write_key(wif)
            return wallet_name
        except:
            click.secho("\n!!!! Error ocurred - wif not imported !!!!!", fg = "bright_red")
    
    def sign_it(self, digest):
        if self.is_watch_only():
            raise RuntimeError("Cannot sign transactions in watch-only mode. This ID is read-only.")
        priv = PrivateKey(self.wif_to_private_key(self.wif()), False)
        sig = priv.ecdsa_sign(digest,True)
        return priv.ecdsa_serialize_compact(sig).hex()
    
    # def update_data(self):
    #     address=self.sidepit_id_manager.load_sidepit_id()
    #     self.sidepit_manager.use_id(address)
    #     self.bitcoin_manager.set_sidepit_id(address)
    #     pass
    
    def update_active_wallet_address(self, new_wallet_name):
        self.active_wallet=new_wallet_name
        self.wallet_file_path = self.FOLDER_WALLETS_PATH / new_wallet_name
    
    def check_if_file_exists(self, name):
        files=os.listdir(self.FOLDER_WALLETS_PATH)
        name = ".sp" + name
        if name in files:
            return True
        return False


    def change_name(self, old_name, new_name):
        old_name = ".sp" + old_name
        new_name = ".sp" + new_name

        # Construct the full paths
        old_file = os.path.join(self.FOLDER_WALLETS_PATH, old_name)
        new_file = os.path.join(self.FOLDER_WALLETS_PATH, new_name)
        os.rename(old_file, new_file)

        if old_name == self.active_wallet:
            self.update_active_wallet_address(new_name)

        
