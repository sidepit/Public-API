import pynng

with pynng.Rep0() as rep:
    rep.listen("tcp://127.0.0.1:5001")
    while True:
        received_message = rep.recv()
        print(received_message.decode())
        rep.send(b"Message: Hello, world!")