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

import pynng
from proto import spapi_pb2
from constants import PROTOCOL, ADDRESS, CLIENT_PORT

class SidepitClient:
    def __init__(self, server_address: str) -> None:
        """
        Initialize the SidepitClient.

        Args:
            server_address (str): The address of the server to connect to.
        """
        self.server_address = server_address
        self.socket = pynng.Pair0()
        self.socket.dial(self.server_address)

    def create_transaction_message(
        self, user_id: bytes, user_signature: bytes
    ) -> spapi_pb2.Transaction:
        """
        Create a new Transaction message.

        Args:
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.

        Returns:
            spapi_pb2.Transaction: The created Transaction message.
        """
        transaction_msg = spapi_pb2.Transaction()
        transaction_msg.version = 1
        transaction_msg.timestamp = int(time.time() * 1e9)  # Nano seconds
        transaction_msg.id = user_id  # User ID bytes
        transaction_msg.signature = user_signature  # User signature bytes
        return transaction_msg

    def send_message(self, message: Union[spapi_pb2.Transaction, bytes]) -> None:
        """
        Send a message over the socket.

        Args:
            message (Union[spapi_pb2.Transaction, bytes]): The message to send.
        """
        if isinstance(message, spapi_pb2.Transaction):
            serialized_msg = message.SerializeToString()
        elif isinstance(message, bytes):
            serialized_msg = message
        else:
            raise ValueError("Message must be of type Transaction or bytes.")

        self.socket.send(serialized_msg)

    def send_new_order(
        self,
        side: bool,
        size: int,
        price: int,
        symbol: str,
        user_id: bytes,
        user_signature: bytes,
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
        transaction_msg = self.create_transaction_message(user_id, user_signature)
        new_order = transaction_msg.new_order
        new_order.side = side
        new_order.size = size
        new_order.price = price
        new_order.symbol = symbol
        self.send_message(transaction_msg)

    def send_cancel_order(
        self, order_id: bytes, user_id: bytes, user_signature: bytes
    ) -> None:
        """
        Send a cancel order message.

        Args:
            order_id (bytes): The ID of the order to cancel.
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.
        """
        transaction_msg = self.create_transaction_message(user_id, user_signature)
        transaction_msg.cancel_orderid = order_id
        self.send_message(transaction_msg)

    def send_auction_bid(
        self,
        epoch: int,
        hash_value: str,
        ordering_salt: str,
        bid: int,
        user_id: bytes,
        user_signature: bytes,
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
        transaction_msg = self.create_transaction_message(user_id, user_signature)
        auction_bid = transaction_msg.auction_bid
        auction_bid.epoch = epoch
        auction_bid.hash = hash_value
        auction_bid.ordering_salt = ordering_salt
        auction_bid.bid = bid
        self.send_message(transaction_msg)

    def close_connection(self) -> None:
        """
        Close the connection to the server.
        """
        self.socket.close()


def main() -> None:
    server_address = f"{PROTOCOL}{ADDRESS}:{CLIENT_PORT}"
    client = SidepitClient(server_address)

    # Example usage
    client.send_new_order(
        side=True,
        size=10,
        price=100,
        symbol="BTCUSD",
        user_id=b"user_id",
        user_signature=b"user_signature",
    )
    client.send_cancel_order(
        order_id=b"order_id",
        user_id=b"user_id",
        user_signature=b"user_signature",
    )
    client.send_auction_bid(
        epoch=1234567890,
        hash_value="hash_value",
        ordering_salt="ordering_salt_value",
        bid=500,
        user_id=b"user_id",
        user_signature=b"user_signature",
    )

    client.close_connection()


if __name__ == "__main__":
    main()
