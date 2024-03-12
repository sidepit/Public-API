import websocket

NODE = "wss://api.sidepit.com/cex"


def on_message(ws, message):
    print(message)


def on_error(ws, error):
    print(f"Error: {error}")


def on_close(ws):
    print("### Closed ###")


def on_open(ws):
    print("### Connected ###")


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(
        NODE, on_message=on_message, on_error=on_error, on_close=on_close
    )
    ws.on_open = on_open
    ws.run_forever()
