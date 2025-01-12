#!/usr/bin/env python3

import time
from datetime import datetime
from typing import Union

import pynng
from proto import spapi_pb2
from constants import PROTOCOL, ADDRESS, CLIENT_PORT
from sidepit_nng_client import SidepitClient

from dotenv import load_dotenv
import os




def main() -> None:

    load_dotenv()
    sidepit_id = os.getenv("SIDEPIT-ID")
    secret_key = os.getenv("SIDEPIT-SECRET")


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