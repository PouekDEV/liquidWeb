from PIL import Image
import frameWriter
import websockets
import asyncio
import driver
import io

lcd = None
frameBuffer = asyncio.Queue(maxsize=10)
PORT = 54217

async def handle_connection(websocket):
    print("Connected to integration runner")
    try:
        async for message in websocket:
            try:
                img = Image.open(io.BytesIO(message))
                frame = await asyncio.to_thread(lcd.imageToFrame, img, True)
                if frameBuffer.full():
                    _ = frameBuffer.get_nowait()
                await frameBuffer.put(frame)
                #print(f"Queue size: {frameBuffer.qsize()}")
            except Exception as e:
                print(f"Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"Encountered an error during connection: {e}")

async def run():
    print(f"Starting WebSocket server on ws://localhost:{PORT}")
    async with websockets.serve(handle_connection, "127.0.0.1", PORT):
        await asyncio.Future()

async def main(LCD):
    global lcd
    lcd = LCD
    lcd.setupStream()
    writer = frameWriter.FrameWriter(frameBuffer, lcd)
    asyncio.create_task(writer.run())
    await run()

if __name__ == "__main__":
    asyncio.run(main(driver.KrakenLCD(50, 90)))