import asyncio
import websockets
import multiprocessing

from skellycam import configure_logging

configure_logging()
import logging
logger = logging.getLogger(__name__)

async def websocket_client(uri: str):
    logger.info(f"Connecting to websocket server at {uri}")
    async with websockets.connect(uri) as websocket:
        logger.success("Connected to websocket server!")
        await websocket.send("Hello, server!")
        while True:
            message = await websocket.recv()
            if isinstance(message, str):
                print(f"\n\nReceived text from server: {message}\n\n")
            elif isinstance(message, bytes):
                print(f"Received binary data of with size: {len(message) / 1024}kb")

def run_client(uri: str):
    asyncio.run(websocket_client(uri))

def start_websocket_client():
    logger.info("\n\nStarting websocket client...\n\n")
    server_uri = "ws://localhost:8003/ws/connect"
    client_process = multiprocessing.Process(target=run_client, args=(server_uri,))
    client_process.start()
    client_process.join()
    logger.info("\n\nWebsocket client finished\n\n")

if __name__ == "__main__":
    start_websocket_client()
    logger.info("Done!")
