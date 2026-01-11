import pynng
from proto import sidepit_api_pb2
from google.protobuf.json_format import ParseDict

class SidepitReqClient:
    """Simple synchronous client for Sidepit Request/Reply API"""
    
    def __init__(self, address=None, protocol="tcp://", host="localhost", port="12125"):
        """Initialize the request client
        
        Args:
            address: Full address string (e.g., "tcp://localhost:12125"). 
                     If provided, overrides protocol/host/port.
            protocol: Protocol to use (default: "tcp://")
            host: Hostname or IP (default: "localhost")
            port: Port number (default: "12125")
        """
        if address is None:
            address = f"{protocol}{host}:{port}"
        
        self.address = address
        self.socket = pynng.Req0()
        self.socket.dial(self.address)
        print(f"Connected to {self.address}")
    
    def _send_request(self, request_dict):
        """Send a request and return the protobuf response"""
        # Create and serialize request
        request = sidepit_api_pb2.RequestReply()
        ParseDict(request_dict, request, ignore_unknown_fields=True)
        serialized = request.SerializeToString()
        
        # Send and receive synchronously
        self.socket.send(serialized)
        response_data = self.socket.recv()
        
        # Parse response
        response = sidepit_api_pb2.ReplyRequest()
        response.ParseFromString(response_data)
        return response
    
    def get_active_product(self, ticker=None):
        """Get active product information
        
        Args:
            ticker: Optional ticker to filter by
            
        Returns:
            ActiveProduct protobuf object
        """
        request_dict = {"TypeMask": sidepit_api_pb2.ACTIVE_PRODUCT}
        if ticker:
            request_dict["ticker"] = ticker
            
        response = self._send_request(request_dict)
        return response.active_product
    
    def get_positions(self, trader_id):
        """Get positions for a trader
        
        Args:
            trader_id: The trader's sidepit ID
            
        Returns:
            TraderPositionOrders protobuf object
        """
        request_dict = {
            "TypeMask": sidepit_api_pb2.POSITIONS,
            "traderid": trader_id
        }
        
        response = self._send_request(request_dict)
        return response.trader_positions
    
    def get_quote(self, ticker=None):
        """Get market quote
        
        Args:
            ticker: Optional ticker to filter by
            
        Returns:
            MarketData protobuf object
        """
        request_dict = {"TypeMask": sidepit_api_pb2.QUOTE}
        if ticker:
            request_dict["ticker"] = ticker
            
        response = self._send_request(request_dict)
        return response.market_data
    
    def close(self):
        """Close connection"""
        self.socket.close()
        print("Connection closed")


def main():
    """Simple CLI demo"""
    print("=== Sidepit Request Client Demo ===")
    print("Connecting to request server...")
    
    client = SidepitReqClient()
    
    print("\n1. Getting active product...")
    try:
        result = client.get_active_product()
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n2. Getting quote...")
    try:
        result = client.get_quote()
        print(result)
    except Exception as e:
        print(f"Error: {e}")
    
    # Example: get positions (uncomment and add trader_id)
    # print("\n3. Getting positions...")
    # try:
    #     result = client.get_positions("your_trader_id_here")
    #     print(result)
    # except Exception as e:
    #     print(f"Error: {e}")
    
    client.close()


if __name__ == "__main__":
    main()
