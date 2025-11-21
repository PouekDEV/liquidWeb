from PIL import Image
import frameWriter
import websockets
import asyncio
import driver
import queue
import time
import io

lcd = None
frameBuffer = queue.Queue(maxsize=10)
PORT = 54217

async def handle_connection(websocket):
    print("Connected to integration runner")
    startTime = time.time()
    try:
        async for message in websocket:
            if frameBuffer.full():
                print("Queue is full!!!")
            else:
                print(f"Queue: {frameBuffer.qsize()}")
            try:
                startTime = time.time()
                img = Image.open(io.BytesIO(message))
                frameBuffer.put((lcd.imageToFrame(img, adaptive=True), startTime, time.time() - startTime))
            except Exception as e:
                print(f"Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"Encountered an error during connection: {e}")

async def run():
    print(f"Starting WebSocket server on ws://localhost:{PORT}")
    async with websockets.serve(handle_connection, "127.0.0.1", PORT):
        await asyncio.Future()

def main(LCD):
    global lcd
    lcd = LCD
    lcd.setupStream()
    Writer = frameWriter.FrameWriter(frameBuffer, lcd)
    Writer.start()
    asyncio.run(run())

if __name__ == "__main__":
    main(driver.KrakenLCD(50, 90))