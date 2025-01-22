import pynng

with pynng.Sub0() as sub:
    sub.dial("tcp://127.0.0.1:5001")
    sub.subscribe(b"")
    while True:
        message = sub.recv()
        print(f"Received: {message.decode()}")