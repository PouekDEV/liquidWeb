import subprocess
import time

p1 = subprocess.Popen(["python", "frameReceiver.py"])
p2 = subprocess.Popen(["python", "hardwareInfo.py"])

try:
    while True:
        time.sleep(1)
        if p1.poll() is not None or p2.poll() is not None:
            print("One process exited, shutting down the other")
            p1.terminate()
            p2.terminate()
            break
except KeyboardInterrupt:
    p1.terminate()
    p2.terminate()