from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn
import pynng
import sidepit_api_pb2
# from spapi_pb2 import ReplyRequestTypes
from google.protobuf.json_format import ParseDict, MessageToJson
import asyncio
import signal
import json

from constants import REQ_PROTOCOL, REQ_ADDRESS, REQ_PORT

app = FastAPI()
req_client = None

class RequestReplyModel(BaseModel):
    TypeMask: int = sidepit_api_pb2.ACTIVE_PRODUCT
    traderid: Optional[str] = None
    ticker: Optional[str] = None

class ReqClient:
    def __init__(self, request_address: str) -> None:
        global req_client
        self.request_address = request_address
        self.socket = pynng.Req0()
        try:
            self.socket.dial(self.request_address)
            print(f"Connected to {self.request_address}.")
        except Exception as e:
            print(f"Failed to connect to {self.request_address}: {e}")
            raise

        self.stack = []
        for i in range(100):
            self.stack.append(self.socket.new_context())

        req_client = self

    async def send_request(self, request_data: dict) -> sidepit_api_pb2.ReplyRequest:
        request = sidepit_api_pb2.RequestReply()
        ParseDict(request_data, request, ignore_unknown_fields=True)

        serialized_request = request.SerializeToString()
        if not serialized_request:
            print("Serialization failed.")
            raise ValueError("Failed to serialize the request.")
        try:
            ctx = self.stack.pop()
            await ctx.asend(serialized_request)
            response_data = await ctx.arecv()
            self.stack.append(ctx)
            if response_data is None:
                raise ValueError("No response received from server.")
            response = sidepit_api_pb2.ReplyRequest()
            response.ParseFromString(response_data)
            # print(response)
            return response
        except Exception as e:
            print(f"Failed to send request: {e}")
            raise

    def close_connection(self) -> None:
        for ctx in self.stack:
            ctx.close()
        self.socket.close()
        print("Connection closed.")


async def execute_request(request_data: dict):
    request_address = f"{REQ_PROTOCOL}{REQ_ADDRESS}:{REQ_PORT}"
    global req_client
    if req_client is None:
        try:
            req_client = ReqClient(request_address)
        except Exception as e:
            print(f"Failed to initialize ReqClient: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    try:
        response = await req_client.send_request(request_data)
        if response.TypeMask == sidepit_api_pb2.POSITIONS:
            return response.trader_positions
        elif response.TypeMask == sidepit_api_pb2.QUOTE:
            return response.market_data
        else:
            return response.active_product

    except Exception as e:
        print(f"Error during request execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/request_position/")
async def request_position(request: RequestReplyModel):
    print(request)
    request.TypeMask = sidepit_api_pb2.POSITIONS
    try:
        response = await execute_request(request.dict())
        json_response = MessageToJson(response, preserving_proto_field_name=True, including_default_value_fields=True)
        # print(json.loads(json_response))

        return {
            "message": "Request processed successfully.",
            "response": json.loads(json_response),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/request_position/{trader_id}")
async def request_position(trader_id: str):
    # print(trader_id)
    request = RequestReplyModel (traderid=trader_id, TypeMask= sidepit_api_pb2.POSITIONS)
    try:
        response = await execute_request(request.dict())
        json_response = MessageToJson(response, preserving_proto_field_name=True, including_default_value_fields=True)
        return json.loads(json_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/active_product/")
@app.post("/active_product/")
async def active_product():
    try:
        request = RequestReplyModel(TypeMask= sidepit_api_pb2.ACTIVE_PRODUCT)
        response = await execute_request(request.dict())
        # print(response)
        json_response = MessageToJson(response, preserving_proto_field_name=True, including_default_value_fields=True)
        return json.loads(json_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quote/")
@app.post("/quote/")
async def active_product():
    try:
        request = RequestReplyModel(TypeMask=sidepit_api_pb2.QUOTE)
        response = await execute_request(request.dict())
        json_response = MessageToJson(response, preserving_proto_field_name=True, including_default_value_fields=True)
        return json.loads(json_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def shutdown(signal, frame):
    print("Shutting down...")
    if req_client is not None:
        req_client.close_connection()
    asyncio.get_event_loop().stop()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    uvicorn.run(app, host="0.0.0.0", port=13125)
