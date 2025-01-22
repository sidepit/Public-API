import pynng
import time

with pynng.Pull0() as pull:
    pull.dial("tcp://127.0.0.1:5001")
    while True:
        received_message = pull.recv()
        print(received_message.decode())
        time.sleep(1)