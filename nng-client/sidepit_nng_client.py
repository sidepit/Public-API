"""
Sidepit Client-Side API Application

This application facilitates communication with the Sidepit server using a client-side API. 
It enables users to perform various actions such as 
sending new orders, canceling orders, and placing bids in auctions.

Components:

1. SidepitClient Class:
   - This class represents the client-side interface for interacting with the Sidepit server.
   - It provides methods for sending different types of messages to the server.
   - Methods include:
     - `create_transaction_message()`: Creates a new transaction message.
     - `send_message()`: Sends a message over the socket.
     - `send_new_order()`: Sends a new order message to the server.
     - `send_cancel_order()`: Sends a cancel order message to the server.
     - `send_auction_bid()`: Sends an auction bid message to the server.
     - `close_connection()`: Closes the connection to the server.

2. Main:
   - Example usage scenarios are demonstrated within the `main()` 

Usage:
1. Instantiate a SidepitClient object with the server address.
2. Use the provided methods to interact with the Sidepit server.
3. Close the connection using `close_connection()` method when done.
"""
import time
from datetime import datetime
from typing import Union
from hashlib import sha256
import pynng
import hashlib
import base58
from secp256k1 import PrivateKey
# from proto import spapi_pb2
import proto.spapi_pb2 as spapi_pb2
# Ensure that spapi_pb2.py is generated from the .proto file and contains the Transaction class
from constants import PROTOCOL, ADDRESS, CLIENT_PORT

class SidepitClient:
    def __init__(self, server_address: str) -> None:
        """
        Initialize the SidepitClient.

        Args:
            server_address (str): The address of the server to connect to.
        """
        self.server_address = server_address
        self.socket = pynng.Push0()
        self.socket.dial(self.server_address)

    # def create_transaction_message(
    #     self, user_id: bytes, user_signature: bytes
    # ) -> spapi_pb2.Transaction:
    #     """
    #     Create a new Transaction message.

    #     Args:
    #         user_id (bytes): The ID of the user.
    #         user_signature (bytes): The signature of the user.

    #     Returns:
    #         spapi_pb2.Transaction: The created Transaction message.
    #     """
    #     transaction_msg = spapi_pb2.Transaction()
    #     transaction_msg.version = 1
    #     transaction_msg.timestamp = int(time.time() * 1e9)  # Nano seconds
    #     transaction_msg.id = user_id  # User ID bytes
    #     transaction_msg.signature = user_signature  # User signature bytes
    #     return transaction_msg
    



    def create_transaction_message(self,user_id: bytes) -> spapi_pb2.SignedTransaction:
        """
        Create a new Transaction message.

        Args:
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.

        Returns:
            sidepit_api_pb2.Transaction: The created Transaction message.
        """
        signedTransaction = spapi_pb2.SignedTransaction()
        transaction_msg = signedTransaction.transaction  
        transaction_msg.version = 1
        transaction_msg.timestamp = int(time.time() * 1e9)   
        transaction_msg.sidepit_id = user_id 

        return signedTransaction
    

    def sign_it(self, digest, wif):
        priv = PrivateKey(self.wif_to_private_key(wif), False)
        sig = priv.ecdsa_sign(digest,True)
        return priv.ecdsa_serialize_compact(sig).hex()


    def sign_digest(self, tx, wif):
        digest = sha256(tx.SerializeToString()).digest() 
        hexsig = self.sign_it(digest, wif); 
        return hexsig


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


    def send_message(self, message: Union[spapi_pb2.SignedTransaction, bytes]) -> None:
        """
        Send a message over the socket.

        Args:
            message (Union[sidepit_api_pb2.Transaction, bytes]): The message to send.
        """
        if isinstance(message, spapi_pb2.SignedTransaction):
            serialized_msg = message.SerializeToString()
        elif isinstance(message, bytes):
            serialized_msg = message
        else:
            raise ValueError("Message must be of type Transaction or bytes.")

        self.socket.send(serialized_msg)

    def send_new_order(
        self,
        side: int,
        size: int,
        price: int,
        symbol: str,
        user_id,
        wif,
    ) -> None:
        """
        Send a new order message.

        Args:
            side (bool): The side of the order (True for buy, False for sell).
            size (int): The size of the order.
            price (int): The price of the order.
            symbol (str): The symbol of the order.
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.
        """
        stx = self.create_transaction_message(user_id)
        new_order = stx.transaction.new_order
        new_order.side = side
        new_order.size = size
        new_order.price = price
        new_order.ticker = symbol

        stx.signature = self.sign_digest(stx.transaction,wif)
        self.send_message(stx)

    def send_cancel_order(
        self, order_id: bytes, user_id, wif) -> None:
        """
        Send a cancel order message.

        Args:
            order_id (bytes): The ID of the order to cancel.
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.
        """

        stx = self.create_transaction_message(user_id)
        stx.transaction.cancel_orderid = order_id
        stx.signature = self.sign_digest(stx.transaction,wif)
        self.send_message(stx)
        return  stx.transaction.sidepit_id + ":" + str(stx.transaction.timestamp)

    # def send_auction_bid(
    #     self,
    #     epoch: int,
    #     hash_value: str,
    #     ordering_salt: str,
    #     bid: int,
    #     user_id: bytes,
    #     user_signature: bytes,
    # ) -> None:
    #     """
    #     Send an auction bid message.

    #     Args:
    #         epoch (int): The epoch time of the bid.
    #         hash_value (str): The hash value.
    #         ordering_salt (str): The ordering salt.
    #         bid (int): The bid value in satoshis.
    #         user_id (bytes): The ID of the user.
    #         user_signature (bytes): The signature of the user.
    #     """
    #     transaction_msg = self.create_transaction_message(user_id, user_signature)
    #     auction_bid = transaction_msg.auction_bid
    #     auction_bid.epoch = epoch
    #     auction_bid.hash = hash_value
    #     auction_bid.ordering_salt = ordering_salt
    #     auction_bid.bid = bid
    #     self.send_message(transaction_msg)

    def close_connection(self) -> None:
        """
        Close the connection to the server.
        """
        self.socket.close()


    def send_auction_bid(
        self,
        epoch: int,
        hash_value: str,
        ordering_salt: str,
        bid: int,
        user_id: bytes,
        wif
    ) -> None:
        """
        Send an auction bid message.

        Args:
            epoch (int): The epoch time of the bid.
            hash_value (str): The hash value.
            ordering_salt (str): The ordering salt.
            bid (int): The bid value in satoshis.
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.
        """

        stx = self.create_transaction_message(user_id)
        auction_bid = stx.transaction.auction_bid
        auction_bid.epoch = epoch
        auction_bid.hash = hash_value
        auction_bid.ordering_salt = ordering_salt
        auction_bid.bid = bid

        stx.signature = self.sign_digest(stx.transaction,wif)
        self.send_message(stx)
        return  stx.transaction.sidepit_id + ":" + str(stx.transaction.timestamp)
