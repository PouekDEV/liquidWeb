from aioxmlrpc.server import SimpleXMLRPCServer
from PIL import Image
import frameWriter
import websockets
import asyncio
import driver
import sys
import io

lcd = None
frameBuffer = asyncio.Queue(maxsize=10)
PORT = 54217

async def handleConnection(websocket):
    print("[FRAME-RECEIVER] Connected to integration runner")
    try:
        async for message in websocket:
            try:
                img = Image.open(io.BytesIO(message))
                frame = await asyncio.to_thread(lcd.imageToFrame, img, True)
                if frameBuffer.full():
                    _ = frameBuffer.get_nowait()
                await frameBuffer.put(frame)
                #print(f"[FRAME-RECEIVER] Queue size: {frameBuffer.qsize()}")
            except Exception as e:
                print(f"[FRAME-RECEIVER] Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"[FRAME-RECEIVER] Encountered an error during connection: {e}")

async def run():
    print(f"[FRAME-RECEIVER] Starting WebSocket server on ws://localhost:{PORT}")
    async with websockets.serve(handleConnection, "127.0.0.1", PORT):
        await asyncio.Future()

async def runXMLRPCServer():
    server = SimpleXMLRPCServer(("localhost", PORT + 2), allow_none=True)
    server.register_function(setFixedSpeed)
    print(f"[FRAME-RECEIVER] Hosting device handle on port {PORT + 2}")
    await server.serve_forever()

async def main(LCD):
    global lcd
    lcd = LCD
    lcd.setupStream()
    writer = frameWriter.FrameWriter(frameBuffer, lcd)
    asyncio.create_task(writer.run())
    asyncio.create_task(runXMLRPCServer())
    await run()

async def setFixedSpeed(channel, duty):
    global lcd
    lcd.setFixedSpeed(channel, duty)

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        brightness = int(sys.argv[1])
        orientation = int(sys.argv[2])
        PORT = int(sys.argv[3])
    else:
        print("[FRAME-RECEIVER] Brightness, orientation and port hasn't been provided")
        sys.exit()
    print(f"[FRAME-RECEIVER] Initiating connection with {brightness}% brightness and orientation of {orientation}°")
    asyncio.run(main(driver.KrakenLCD(brightness, orientation)))