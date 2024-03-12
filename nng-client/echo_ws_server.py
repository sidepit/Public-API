import asyncio
import websockets
from echo_nng_client import EchoClient
from constants import PROTOCOL, ADDRESS, ECHO_PORT, WS_ECHO_PORT

clients = set()
async def ws_handler(websocket, path):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)


async def main():
    echo_address = f"{PROTOCOL}{ADDRESS}:{ECHO_PORT}"
    echo_client = EchoClient(echo_address, clients)

    start_server = websockets.serve(ws_handler, "localhost", int(WS_ECHO_PORT))

    print("Subscribing to feed and starting WebSocket server...")
    await asyncio.gather(echo_client.receive_messages(), start_server)
    

if __name__ == "__main__":
    asyncio.run(main())
