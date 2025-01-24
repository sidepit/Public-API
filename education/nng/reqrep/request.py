import pynng
import time

with pynng.Req0() as req:
    req.dial("tcp://127.0.0.1:5001")
    while True:
        req.send(b"Send me a message...")
        reply = req.recv()
        print(reply.decode())
        time.sleep(1)