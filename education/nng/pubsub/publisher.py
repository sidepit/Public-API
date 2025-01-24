import pynng
import time

with pynng.Pub0() as pub:
    pub.listen("tcp://127.0.0.1:5001")
    while True:
        pub.send(b"Hello, from Sidepit!")
        time.sleep(1)