import json


async def broadcast(clients, message):
    to_remove = set()
    for client in clients:
        try:
            await client.send(message)
        except:
            to_remove.add(client)
    for client in to_remove:
        clients.discard(client)  # Use discard to avoid KeyError if already removed
