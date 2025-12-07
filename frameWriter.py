import asyncio
import driver

class FrameWriter:
    def __init__(self, frameBuffer: asyncio.Queue, lcd: driver.KrakenLCD):
        self.frameBuffer = frameBuffer
        self.lcd = lcd
    async def run(self):
        while True:
            await self.onFrame()
    async def onFrame(self):
        frame = await self.frameBuffer.get()
        try:
            await asyncio.to_thread(self.lcd.writeFrame, frame)
        except Exception:
            pass