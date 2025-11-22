import subprocess
import time
import sys

orientation = 0
brightness = 0
fps = 0
url = ""
configuration = 0
width = 0
height = 0
PORT = 54217

argumentsCount = len(sys.argv)
minimum = False

def notEnoughArguments():
    print("[MAIN] Not enough arguments provided")
    print("[MAIN] Usage: liquidWeb configuration (0-1) url fps (0-30) brightness (0-100%) orientation (0-360°) port (Optional. Will use the selected one plus the next one. Default 54217,54218)")
    exit()

if argumentsCount >= 3:
    configuration = sys.argv[1]
    url = sys.argv[2]
    if argumentsCount == 3:
        minimum = True
else:
    notEnoughArguments()
if argumentsCount >= 6:
    fps = sys.argv[3]
    brightness = sys.argv[4]
    orientation = sys.argv[5]
else:
    if not minimum:
        notEnoughArguments()
if argumentsCount >= 7:
    PORT = sys.argv[6]

if argumentsCount == 3:
    width = 1280
    height = 720
    fps = 60
else:
    width = 640
    height = 640
    configuration = 0

p1 = subprocess.Popen(["./integration-runner/out/integration-runner-win32-x64/integration-runner.exe", f"--width={width}", f"--height={height}", f"--fps={fps}", f"--configuration={configuration}", f"--url={url}", f"--port={PORT}"])
if argumentsCount >= 5:
    p2 = subprocess.Popen(["python", "frameReceiver.py", f"{brightness}", f"{orientation}", f"{PORT}"])
    p3 = subprocess.Popen(["python", "hardwareServer.py", f"{int(PORT)+1}"])

try:
    while True:
        time.sleep(1)
        if argumentsCount >= 6:
            if p1.poll() is not None or p2.poll() is not None or p3.poll() is not None:
                print("[MAIN] One process exited, shutting down the other")
                p1.terminate()
                p2.terminate()
                p3.terminate()
                break
        else:
            if p1.poll() is not None:
                print("[MAIN] Integration runner closed")
                p1.terminate()
                break
except KeyboardInterrupt:
    p1.terminate()
    if argumentsCount >= 6:
        p2.terminate()
        p3.terminate()