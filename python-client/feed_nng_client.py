import asyncio
import pynng
from proto import sidepit_api_pb2
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
        self.latest_messages = {}  # Store by ticker

    async def receive_messages(self) -> None:
        try:
            while True:
                serialized_msg = await self.socket.arecv()
                await self.broadcast_message(serialized_msg)
        except KeyboardInterrupt:
            print("Stopping subscription...")
        except Exception:
            # Socket was closed or other error occurred
            pass

    async def broadcast_message(self, serialized_msg: bytes) -> None:
        market_data = sidepit_api_pb2.MarketData()
        market_data.ParseFromString(serialized_msg)
        json_message = MessageToJson(market_data,preserving_proto_field_name=True)
        
        # Parse and store by ticker
        data = json.loads(json_message)
        ticker = data.get("ticker")
        if ticker:
            self.latest_messages[ticker] = json_message
        
        # Only broadcast if there are clients (not None means silent mode)
        if self.clients is not None:
            if self.clients:  # If set is not empty
                await broadcast(self.clients, json_message)
        else:
            # Print when running standalone (clients is None)
            print(f"Received: {json_message}")

    def close_connection(self) -> None:
        self.socket.close()

    def get_latest(self, ticker=None):
        """Get the most recent message(s)
        
        Args:
            ticker: Optional ticker to filter by. If None, returns all latest messages.
        
        Returns:
            If ticker is specified: JSON string of that ticker's latest message
            If ticker is None: Dictionary of all tickers and their latest messages
        """
        if ticker:
            return self.latest_messages.get(ticker)
        return self.latest_messages

async def main():
    feed_address = f"{PROTOCOL}{ADDRESS}:{FEED_PORT}"
    feed_client = FeedClient(feed_address, set())

    print("Subscribing to feed...")
    await feed_client.receive_messages()

if __name__ == "__main__":
    asyncio.run(main())
