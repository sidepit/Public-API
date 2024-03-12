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
        # print(market_data)
        # json_obj = MessageToJson(market_data,preserving_proto_field_name=True)
        # print(json_obj)
        # message = {
        #     "version": market_data.version,
        #     "epoch": market_data.epoch,
        #     "bar": {},
        #     "quote": {},
        # }
        # if market_data.HasField("bar"):
        #     message["bar"] = {
        #         "symbol": market_data.bar.symbol,
        #         "epoch": market_data.bar.epoch,
        #         "open": market_data.bar.open,
        #         "high": market_data.bar.high,
        #         "low": market_data.bar.low,
        #         "close": market_data.bar.close,
        #         "volume": market_data.bar.volume,
        #     }
        # if market_data.HasField("quote"):
        #     message["quote"] = {
        #         "bidsize": market_data.quote.bidsize,
        #         "bid": market_data.quote.bid,
        #         "ask": market_data.quote.ask,
        #         "asksize": market_data.quote.asksize,
        #         "last": market_data.quote.last,
        #         "lastsize": market_data.quote.lastsize,
        #         "upordown": market_data.quote.upordown,
        #         "symbol": market_data.quote.symbol,
        #         "epoch": market_data.quote.epoch,
        #     }
        await broadcast(self.clients, MessageToJson(market_data,preserving_proto_field_name=True))

    def close_connection(self) -> None:
        self.socket.close()
