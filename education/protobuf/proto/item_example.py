from google.protobuf.json_format import MessageToJson
import item_pb2

item = item_pb2.Item()

item.id = 1
item.name = "Flashlight 🔦"
item.rating = "⭐️⭐️⭐️"
item.in_stock = True

data_serialized = item.SerializeToString()

item.ParseFromString(data_serialized)

print(f"Id: {item.id}")
print(f"Name: {item.name}")
print(f"Rating: {item.rating}")
print(f"In Stock: {item.in_stock}")

# Convert Protobuf to JSON!
print("JSON Output:")
print(MessageToJson(item, indent=2))