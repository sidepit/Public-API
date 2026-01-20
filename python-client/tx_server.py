from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import pynng
from sidepit_api_pb2 import SignedTransaction 
from google.protobuf.json_format import ParseDict
import asyncio
import signal
from typing import Optional, Dict

from constants import PUBLISH_PROTOCOL, PUBLISH_ADDRESS, PUBLISH_PORT

app = FastAPI()

pub_client = None

class TransactionModel(BaseModel):
    version: int
    timestamp: int
    newOrder: Optional[Dict] = None
    new_order: Optional[Dict] = None
    cancel_orderid: Optional[str] = None
    cancelOrderid: Optional[str] = None
    sidepit_id: str

class SignedTransactionModel(BaseModel):
    transaction: TransactionModel
    signature: str

class PubClient:
    def __init__(self, publish_address: str) -> None:
        global pub_client
        self.publish_address = publish_address
        self.socket = pynng.Push0()
        try:
            self.socket.dial(self.publish_address)
            print(f"Connected to {self.publish_address}.")
        except pynng.exceptions.NngException as e:
            print(f"Failed to connect to {self.publish_address}: {e}")
            raise
        pub_client = self

    async def send_transaction(self, new_tx: dict) -> None:
        transaction = SignedTransaction()
        ParseDict(new_tx, transaction, ignore_unknown_fields=True)
        print("transaction", transaction)

        serialized_msg = transaction.SerializeToString()
        try:
            await self.socket.asend(serialized_msg)
            print("Transaction sent.")
        except pynng.exceptions.NngException as e:
            print(f"Failed to send transaction: {e}")

    def close_connection(self) -> None:
        self.socket.close()
        print("Connection closed.")


async def execute_tx(new_tx: dict):
    publish_address = f"{PUBLISH_PROTOCOL}{PUBLISH_ADDRESS}:{PUBLISH_PORT}"
    global pub_client
    if pub_client is None:
        try:
            pub_client = PubClient(publish_address)
        except Exception as e:
            print(f"Failed to initialize PubClient: {e}")
            return {"error": str(e)}

    try:
        await pub_client.send_transaction(new_tx)
    except Exception as e:
        print(f"Error during transaction sending: {e}")
        return {"error": str(e)}


@app.post("/transaction/")
async def post_transaction(transaction: SignedTransactionModel):
    print(transaction)
    try:
        await execute_tx(transaction.dict())
        return {"message": "Transaction processed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def shutdown(signal, frame):
    print("Shutting down...")
    if pub_client is not None:
        pub_client.close_connection()
    asyncio.get_event_loop().stop()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    uvicorn.run(app, host="0.0.0.0", port=13121)
