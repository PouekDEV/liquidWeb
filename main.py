import driver
import frameReceiver
import hardwareInfo
from threading import Thread
from time import sleep

LCD = driver.KrakenLCD(50, 90)

class FrameWriterRunner(Thread):
    def __init__(self):
        super().__init__(name="FrameWriterRunner")
        self.daemon = True
    def run(self):
        frameReceiver.main(LCD)

class HardwareInfoRunner(Thread):
    def __init__(self):
        super().__init__(name="HardwareInfoRunner")
        self.daemon = True
    def run(self):
        hardwareInfo.main(LCD)

def main():
    rFW = FrameWriterRunner()
    rHIS = HardwareInfoRunner()
    rFW.start()
    rHIS.start()
    try:
        while True:
            sleep(1)
            if not (rFW.is_alive() and rHIS.is_alive()):
                raise KeyboardInterrupt("Some thread is dead")
    except KeyboardInterrupt:
        exit()

if __name__ == "__main__":
    main()