import asyncio
import websockets
import multiprocessing

async def websocket_client(uri: str):

    async with websockets.connect(uri) as websocket:
        await websocket.send("Hello Server!")
        response = await websocket.recv()
        print(f"Received from server: {response}")

def start_client_process(uri: str):

    asyncio.run(websocket_client(uri))

def start_websocket_client():
    print("Starting simple websocket client...")
    server_uri = "ws://localhost:8003/ws/connect"
    client_process = multiprocessing.Process(target=start_client_process, args=(server_uri,))
    client_process.start()
    client_process.join()

if __name__ == "__main__":
    start_websocket_client()
