from playwright.sync_api import sync_playwright
from workers import FrameWriter
from threading import Thread
from utils import debug
from PIL import Image
import driver
import queue
import time
import io

lcd = driver.KrakenLCD()
lcd.setupStream()

class RawProducer(Thread):
    def __init__(self, rawBuffer, url):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.url = url
    def run(self):
        with sync_playwright() as playwright:
            browser = playwright.firefox.launch()
            page = browser.new_page()
            page.set_viewport_size({"width": lcd.resolution.width, "height": lcd.resolution.height})
            page.goto(self.url)
            debug("Screencap worker started")
            while True:
                if self.rawBuffer.full():
                    time.sleep(0.005)
                    continue
                startTime = time.time()
                screenshot = page.screenshot()
                self.rawBuffer.put((screenshot, time.time() - startTime))

class FrameProducer(Thread):
    def __init__(self, rawBuffer, frameBuffer, rotation):
        Thread.__init__(self)
        self.daemon = True
        self.rawBuffer = rawBuffer
        self.frameBuffer = frameBuffer
        self.rotation = rotation
    def run(self):
        print("Image converter worker started")
        while True:
            if self.frameBuffer.full():
                time.sleep(0.001)
                continue
            (screenshot, rawTime) = self.rawBuffer.get()
            startTime = time.time()
            img = Image.open(io.BytesIO(screenshot)).convert("RGBA").rotate(self.rotation)
            self.frameBuffer.put((lcd.imageToFrame(img, adaptive=True), rawTime, time.time() - startTime))

rawBuffer = queue.Queue(maxsize=1)
frameBuffer = queue.Queue(maxsize=1)
rawProducer = RawProducer(rawBuffer, "https://box.pouekdev.one/preview/content?f=6c414c4bec054872e9c9e69ddd2e9e")
frameProducer = FrameProducer(rawBuffer, frameBuffer, 90)
frameWriter = FrameWriter(frameBuffer, lcd)
rawProducer.start()
frameProducer.start()
frameWriter.start()
try:
    while True:
        time.sleep(1)
        if not (
            rawProducer.is_alive()
            and frameProducer.is_alive()
            and frameWriter.is_alive()
        ):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    frameWriter.shouldStop = True
    frameWriter.join()
    exit()