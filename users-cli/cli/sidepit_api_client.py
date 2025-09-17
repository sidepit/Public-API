import sidepit_api_pb2
import json
import time
import requests
from id_manager import SidepitIDManager
from hashlib import sha256  
from google.protobuf.json_format import MessageToJson
from constants import SIDEPIT_API_URL

class SidepitApiClient:
    def __init__(self, id: str, sid: SidepitIDManager) -> None:
        self.sidepit_id = id 
        self.ticker = "USDBTCz24"
        self.idmanager = sid

    def create_transaction_message(self) -> sidepit_api_pb2.SignedTransaction:
        """
        Create a new Transaction message.

        Args:
            user_id (bytes): The ID of the user.
            user_signature (bytes): The signature of the user.

        Returns:
            sidepit_api_pb2.Transaction: The created Transaction message.
        """
        signedTransaction = sidepit_api_pb2.SignedTransaction()
        transaction_msg = signedTransaction.transaction  
        transaction_msg.version = 1
        transaction_msg.timestamp = int(time.time() * 1e9)   
        transaction_msg.sidepit_id = self.sidepit_id 

        return signedTransaction


    def sign_digest(self, tx):
        digest = sha256(tx.SerializeToString()).digest() 
        hexsig = self.idmanager.sign_it(digest); 
        return hexsig

    def do_neworder(self, side, price, size):
        """Place a new order."""
        # Construct the side
        
        stx = self.create_transaction_message()
        new_order = stx.transaction.new_order
        new_order.side = side
        new_order.size = size
        new_order.price = price
        new_order.ticker = self.ticker

        stx.signature = self.sign_digest(stx.transaction)


        json_message = json.loads(MessageToJson(stx, preserving_proto_field_name=True))
        print (json_message)

        # json_message = '{ "transaction": { "version": 1, "timestamp": 1733196967903, "newOrder": { "side": -1, "size": 2, "price": 1111,"ticker": "usdbtcz24"},"sidepit_id": "bc1qkl80muggyp9aqn8th0vdpudmt4zftd97ms4rg5"},"signature": "1de61805dbce4149d1e2d44ebb49ed06696b5b7d7363cd5f4033fd827ed2e29a2c44f5d736abeb654b2bc514c9166e622d36d82d92ea0e8d9b1bc87a8ff3abd6"}'

        ret = self.send_order_to_api(json_message)
        # print(ret)
        

    def send_order_to_api(self, payload):
        api_url = SIDEPIT_API_URL + "transaction/"  # Replace with actual API endpoint
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(api_url, data=json.dumps(payload), headers=headers)
            return response.json()
        except requests.RequestException as e:
            return {"status": "error", "error": str(e)}
