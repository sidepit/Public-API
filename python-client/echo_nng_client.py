import asyncio
import pynng
from proto import spapi_pb2
from utils import broadcast
import json
from constants import PROTOCOL, ADDRESS, ECHO_PORT
from google.protobuf.json_format import MessageToJson

class EchoClient:
    def __init__(self, echo_address: str, clients) -> None:
        self.echo_address = echo_address
        self.socket = pynng.Sub0()
        self.socket.dial(self.echo_address)
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
        txblockstream = spapi_pb2.TxBlockStream()
        txblockstream.ParseFromString(serialized_msg)
        # print(txblockstream)
        await broadcast(self.clients, MessageToJson(txblockstream,preserving_proto_field_name=True))

    def close_connection(self) -> None:
        self.socket.close()
