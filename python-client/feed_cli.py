import asyncio
import threading
from feed_nng_client import FeedClient
from constants import PROTOCOL, ADDRESS, FEED_PORT

class FeedCLI:
    def __init__(self):
        self.feed_client = None
        self.loop = None
        self.thread = None
        
    def start_background_feed(self):
        """Start the feed client in a background thread"""
        feed_address = f"{PROTOCOL}{ADDRESS}:{FEED_PORT}"
        self.feed_client = FeedClient(feed_address, set())
        
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
        print("Feed client started in background...")
        
    def get_latest(self):
        """Get the latest message"""
        if not self.feed_client:
            return "Feed client not started. Run 'start' first."
        
        latest = self.feed_client.get_latest()
        if latest:
            return latest
        else:
            return "No messages received yet."
    
    def stop(self):
        """Stop the feed client"""
        if self.feed_client:
            # Closing the socket will cause arecv to raise an exception
            # and the receive_messages loop will exit
            self.feed_client.close_connection()
        print("Feed client stopped.")

def main():
    cli = FeedCLI()
    
    print("Feed CLI - Commands: start, latest, stop, exit")
    
    while True:
        command = input("\n> ").strip().lower()
        
        if command == "start":
            cli.start_background_feed()
        elif command == "latest":
            print(cli.get_latest())
        elif command == "stop":
            cli.stop()
        elif command == "exit":
            cli.stop()
            break
        else:
            print("Unknown command. Use: start, latest, stop, exit")

if __name__ == "__main__":
    main()
