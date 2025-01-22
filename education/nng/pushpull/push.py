import pynng

with pynng.Push0() as push:
    push.listen("tcp://127.0.0.1:5001")
    while True:
        push.send(b"Hello from push")