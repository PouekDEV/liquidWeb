from aioxmlrpc.server import SimpleXMLRPCServer
from PIL import Image
import websockets
import asyncio
import driver
import sys
import io

lcd = None
frame_buffer = asyncio.Queue(maxsize=10)
PORT = 54217

class FrameWriter:
    def __init__(self, frame_buffer, lcd):
        self.frame_buffer = frame_buffer
        self.lcd = lcd
    async def run(self):
        while True:
            await self.on_frame()
    async def on_frame(self):
        frame = await self.frame_buffer.get()
        try:
            await asyncio.to_thread(self.lcd.write_frame, frame)
        except Exception:
            pass

async def handle_connection(websocket):
    print("[FRAME-WRITER] Connected to integration runner")
    try:
        async for message in websocket:
            try:
                img = Image.open(io.BytesIO(message))
                frame = await asyncio.to_thread(lcd.image_to_frame, img, True)
                if frame_buffer.full():
                    _ = frame_buffer.get_nowait()
                await frame_buffer.put(frame)
                #print(f"[FRAME-WRITER] Queue size: {frameBuffer.qsize()}")
            except Exception as e:
                print(f"[FRAME-WRITER] Encountered an error while getting a response: {e}")
    except Exception as e:
        print(f"[FRAME-WRITER] Encountered an error during connection: {e}")

async def run():
    print(f"[FRAME-WRITER] Starting WebSocket server on ws://localhost:{PORT}")
    async with websockets.serve(handle_connection, "127.0.0.1", PORT):
        await asyncio.Future()

async def run_XMLRPC_server():
    server = SimpleXMLRPCServer(("localhost", PORT + 2), allow_none=True)
    server.register_function(set_fixed_speed)
    server.register_function(get_stats)
    print(f"[FRAME-WRITER] Hosting device handle on port {PORT + 2}")
    await server.serve_forever()

async def main(LCD):
    global lcd
    lcd = LCD
    lcd.setup_stream()
    writer = FrameWriter(frame_buffer, lcd)
    asyncio.create_task(writer.run())
    asyncio.create_task(run_XMLRPC_server())
    await run()

async def set_fixed_speed(channel, duty):
    global lcd
    lcd.set_fixed_speed(channel, duty)

async def get_stats():
    global lcd
    return lcd.get_stats()

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        brightness = int(sys.argv[1])
        orientation = int(sys.argv[2])
        PORT = int(sys.argv[3])
    else:
        print("[FRAME-WRITER] Brightness, orientation and port hasn't been provided")
        sys.exit()
    print(f"[FRAME-WRITER] Initiating connection with {brightness}% brightness and orientation of {orientation}°")
    asyncio.run(main(driver.KrakenLCD(brightness, orientation)))