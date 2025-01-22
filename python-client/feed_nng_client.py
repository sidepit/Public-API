import asyncio
import pynng
from proto import ogcex_pb2
from utils import broadcast
import json
from constants import PROTOCOL, ADDRESS, FEED_PORT
from google.protobuf.json_format import MessageToJson

class FeedClient:
    def __init__(self, feed_address: str, clients) -> None:
        self.feed_address = feed_address
        self.socket = pynng.Sub0()
        self.socket.dial(self.feed_address)
        self.socket.subscribe(b"")
        self.clients = clients

    async def receive_messages(self) -> None:
        try:
            while True:
                serialized_msg = await self.socket.arecv()
                await self.broadcast_message(serialized_msg)
        except KeyboardInterrupt:
            print("Stopping subscription...")

    async def broadcast_message(self, serialized_msg: bytes) -> None:
        market_data = ogcex_pb2.MarketData()
        market_data.ParseFromString(serialized_msg)
        await broadcast(self.clients, MessageToJson(market_data,preserving_proto_field_name=True))

    def close_connection(self) -> None:
        self.socket.close()
