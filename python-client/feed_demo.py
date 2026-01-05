import asyncio
import threading
from feed_nng_client import FeedClient
from constants import PROTOCOL, ADDRESS, FEED_PORT
from fastapi import FastAPI
import uvicorn
import websockets
import json

class FeedDemo:
    def __init__(self):
        self.feed_client = None
        self.loop = None
        self.thread = None
        
    def start_background_feed(self, silent=False):
        """Start the feed client in a background thread"""
        feed_address = f"{PROTOCOL}{ADDRESS}:{FEED_PORT}"
        # Pass None to enable silent mode (no console printing)
        clients = set() if silent else None
        self.feed_client = FeedClient(feed_address, clients)
        
        def run_async_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self.feed_client.receive_messages())
            except Exception:
                # Socket closed or loop stopped
                pass
        
        self.thread = threading.Thread(target=run_async_loop, daemon=True)
        self.thread.start()
        if not silent:
            print("Feed client started in background...")
        
    def get_latest(self, ticker=None):
        """Get the latest message(s)"""
        if not self.feed_client:
            return "Feed client not started. Run 'start' first."
        
        latest = self.feed_client.get_latest(ticker)
        if ticker:
            return latest if latest else "No messages received yet."
        else:
            return latest if latest else {}
    
    def stop(self):
        """Stop the feed client"""
        if self.feed_client:
            # Closing the socket will cause arecv to raise an exception
            # and the receive_messages loop will exit
            self.feed_client.close_connection()
        print("Feed client stopped.")

# CLI Mode
def run_cli():
    demo = FeedDemo()
    
    print("Feed CLI - Commands: start, latest, stop, exit")
    
    while True:
        command = input("\n> ").strip().lower()
        
        if command == "start":
            demo.start_background_feed()
        elif command == "latest":
            print(demo.get_latest())
        elif command == "stop":
            demo.stop()
        elif command == "exit":
            demo.stop()
            break
        else:
            print("Unknown command. Use: start, latest, stop, exit")

# WebSocket Client Mode
async def run_websocket_client():
    from constants import WS_FEED_PORT
    ws_url = f"ws://localhost:{WS_FEED_PORT}"
    
    print(f"Connecting to WebSocket at {ws_url}...")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("Connected! Receiving messages...")
            while True:
                message = await websocket.recv()
                print(f"Received: {message}")
    except KeyboardInterrupt:
        print("\nDisconnected.")
    except Exception as e:
        print(f"Error: {e}")

# HTTP API Mode
def run_http_api():
    demo = FeedDemo()
    demo.start_background_feed(silent=True)  # Silent mode for HTTP API
    
    app = FastAPI()
    
    @app.post("/quote/")
    @app.get("/quote/")
    async def get_quote():
        """Get all latest quotes"""
        latest = demo.get_latest()
        if latest:
            # Parse all JSON strings into objects
            parsed_data = {ticker: json.loads(msg) for ticker, msg in latest.items()}
            return {"status": "success", "data": parsed_data}
        return {"status": "error", "message": "No data available"}
    
    @app.post("/quote/{ticker}")
    @app.get("/quote/{ticker}")
    async def get_quote_by_ticker(ticker: str):
        """Get the latest quote for a specific ticker"""
        latest = demo.get_latest(ticker)
        if latest and latest != "No messages received yet.":
            return {"status": "success", "data": json.loads(latest)}
        return {"status": "error", "message": f"Ticker {ticker} not found"}
    
    print("Starting HTTP API server on http://localhost:8000")
    print("Endpoints:")
    print("  GET  http://localhost:8000/quote/")
    print("  POST http://localhost:8000/quote/")
    print("  GET  http://localhost:8000/quote/{ticker}")
    print("  POST http://localhost:8000/quote/{ticker}")
    print("\nExample: http://localhost:8000/quote/USDBTCH26")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

def main():
    print("=== Feed Demo ===")
    print("Select mode:")
    print("1. CLI - Interactive command-line interface")
    print("2. WebSocket Client - Connect to WebSocket feed server")
    print("3. HTTP API - Run REST API server with /quote/ endpoints")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        run_cli()
    elif choice == "2":
        asyncio.run(run_websocket_client())
    elif choice == "3":
        run_http_api()
    else:
        print("Invalid choice. Exiting.")

if __name__ == "__main__":
    main()
