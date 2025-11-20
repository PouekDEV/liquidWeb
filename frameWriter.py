from workers import FrameWriter
from PIL import Image
import websockets
import asyncio
import driver
import queue
import time
import io

lcd = driver.KrakenLCD(50, 90)
lcd.setupStream()
frameBuffer = queue.Queue(maxsize=10)
PORT = 54217

async def handle_connection(websocket):
    print("Connected to integration runner")
    startTime = time.time()
    try:
        async for message in websocket:
            try:
                startTime = time.time()
                img = Image.open(io.BytesIO(message))
                frameBuffer.put((lcd.imageToFrame(img, adaptive=True), startTime, time.time() - startTime))
            except Exception as e:
                print(f"Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"Encountered an error during connection: {e}")

frameWriter = FrameWriter(frameBuffer, lcd)
frameWriter.start()

async def main():
    print(f"Starting WebSocket server on ws://localhost:{PORT}")
    async with websockets.serve(handle_connection, "127.0.0.1", PORT):
        await asyncio.Future()