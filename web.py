from workers import FrameWriter
from PIL import Image
import websockets
import asyncio
import driver
import queue
import time
import io

lcd = driver.KrakenLCD()
lcd.setupStream()
frameBuffer = queue.Queue(maxsize=10)
rotation = 90

async def handle_connection(websocket):
    print("Connected to integration runner")
    startTime = time.time()
    try:
        async for message in websocket:
            try:
                startTime = time.time()
                img = Image.open(io.BytesIO(message)).rotate(rotation)
                frameBuffer.put((lcd.imageToFrame(img, adaptive=True), startTime, time.time() - startTime))
            except Exception as e:
                print(f"Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"Encountered an error during connection: {e}")

frameWriter = FrameWriter(frameBuffer, lcd)
frameWriter.start()

print("Frame writer started")

async def main():
    print("Starting WebSocket server on ws://localhost:8765")
    async with websockets.serve(handle_connection, "127.0.0.1", 8765):
        await asyncio.Future()

asyncio.run(main())