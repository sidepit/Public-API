import sidepit_api_pb2
import json
import time
import requests
from id_manager import SidepitIDManager
from hashlib import sha256  
from google.protobuf.json_format import MessageToJson
from constants import SIDEPIT_API_URL
import pynng

class SidepitApiClient:
    def __init__(self, sidepit_manager, id_manager: SidepitIDManager) -> None:
        self.sidepit_manager = sidepit_manager  # Reference to get current ticker and ID
        self.idmanager = id_manager
        self.socket = None
        self._init_socket()
    
    def _init_socket(self):
        """Initialize pynng Push0 socket for sending transactions"""
        try:
            from constants import PUBLISH_PROTOCOL, PUBLISH_ADDRESS, PUBLISH_PORT
            publish_address = f"{PUBLISH_PROTOCOL}{PUBLISH_ADDRESS}:{PUBLISH_PORT}"
            self.socket = pynng.Push0()
            self.socket.dial(publish_address)
            print(f"Connected to {publish_address}")
        except Exception as e:
            print(f"Failed to connect to publish socket: {e}")
            self.socket = None

    def create_transaction_message(self) -> sidepit_api_pb2.SignedTransaction:
        """
        Create a new Transaction message.

        Args:
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.

        Returns:
            sidepit_api_pb2.Transaction: The created Transaction message.
        """
        signedTransaction = sidepit_api_pb2.SignedTransaction()
        transaction_msg = signedTransaction.transaction  
        transaction_msg.version = 1
        transaction_msg.timestamp = int(time.time() * 1e9)   
        # Get current sidepit_id from manager (handles wallet switching)
        transaction_msg.sidepit_id = self.sidepit_manager.sidepit_id

        return signedTransaction


    def sign_digest(self, tx):
        digest = sha256(tx.SerializeToString()).digest() 
        hexsig = self.idmanager.sign_it(digest); 
        return hexsig

    def do_neworder(self, side, price, size):
        """Place a new order."""
        stx = self.create_transaction_message()
        new_order = stx.transaction.new_order
        new_order.side = side
        new_order.size = size
        new_order.price = price
        # Get current active ticker from manager (handles ticker switching)
        new_order.ticker = self.sidepit_manager.active_ticker

        stx.signature = self.sign_digest(stx.transaction)

        # Send protobuf directly via pynng
        if self.socket:
            serialized_msg = stx.SerializeToString()
            try:
                self.socket.send(serialized_msg)
                print(f"Transaction sent: {side} {size}@{price}")
                print(stx)
            except Exception as e:
                print(f"Failed to send transaction: {e}")
        else:
            print("Socket not connected, cannot send transaction")

    def do_cancel(self, oid):
        """Cancel an order."""
        stx = self.create_transaction_message()
        stx.transaction.cancel_orderid = oid
        stx.signature = self.sign_digest(stx.transaction)

        # Send protobuf directly via pynng
        if self.socket:
            serialized_msg = stx.SerializeToString()
            try:
                self.socket.send(serialized_msg)
                print(f"Cancel transaction sent: {oid}")
                print(stx)
            except Exception as e:  
                print(f"Failed to send transaction: {e}")
        else:
            print("Socket not connected, cannot send transaction")


    def close_connection(self):
        """Close the pynng socket connection"""
        if self.socket:
            self.socket.close()
            print("Connection closed.")
