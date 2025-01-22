from websockets.sync.client import connect
import json

def client():
    with connect("ws://localhost:13122") as websocket:
        # websocket.send("Hello world!")
        message = websocket.recv()
        print(message)

client()