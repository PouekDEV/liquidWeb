import asyncio

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