import asyncio
import websockets
from feed_nng_client import FeedClient
from constants import PROTOCOL, ADDRESS, FEED_PORT, WS_FEED_PORT

clients = set()

async def ws_handler(websocket, path):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)

async def main():
    feed_address = f"{PROTOCOL}{ADDRESS}:{FEED_PORT}"
    feed_client = FeedClient(feed_address, clients)

    start_server = websockets.serve(ws_handler, "localhost", int(WS_PORT))

    print("Subscribing to feed and starting WebSocket server...")
    await asyncio.gather(feed_client.receive_messages(), start_server)


if __name__ == "__main__":
    asyncio.run(main())
