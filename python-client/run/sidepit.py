from proto import sidepit_api_pb2
from google.protobuf.json_format import MessageToJson
import pynng

with pynng.Sub0() as sub:
    sub.dial("tcp://api.sidepit.com:12123")
    sub.subscribe(b"")
    while True:
        message = sub.recv()
        obj = sidepit_api_pb2.TxBlockStream()
        obj.ParseFromString(message)
        print(MessageToJson(obj, preserving_proto_field_name=True))