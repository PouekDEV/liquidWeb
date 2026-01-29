import subprocess
import signal
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

arguments_count = len(sys.argv)
minimum = False

def not_enough_arguments():
    print("[MAIN] Not enough arguments provided")
    print("[MAIN] Usage: liquidWeb configuration (0-1) url fps (0-30) brightness (0-100%) orientation (0-360°) port (Optional. Will use the selected one plus two next ones. Default 54217, 54218, 54219)")
    sys.exit()

if arguments_count >= 3:
    configuration = sys.argv[1]
    url = sys.argv[2]
    if arguments_count == 3:
        minimum = True
else:
    not_enough_arguments()
if arguments_count >= 6:
    fps = sys.argv[3]
    if fps > 30:
        print("[MAIN] Can't set more than 30 fps")
        fps = 30
    brightness = sys.argv[4]
    orientation = sys.argv[5]
else:
    if not minimum:
        not_enough_arguments()
if arguments_count >= 7:
    PORT = sys.argv[6]

if arguments_count == 3:
    width = 1280
    height = 720
    fps = 60
else:
    width = 640
    height = 640
    configuration = 0

#subprocess.call("taskkill /im integration-runner.exe /f /t")
#subprocess.call("taskkill /im frame-receiver.exe /f /t")
#subprocess.call("taskkill /im hardware-server.exe /f /t")

p1 = subprocess.Popen(["./modules/integration-runner-linux-x64/integration-runner", f"--width={width}", f"--height={height}", f"--fps={fps}", f"--configuration={configuration}", f"--url={url}", f"--port={PORT}"])
if arguments_count >= 5:
    p2 = subprocess.Popen(["./modules/frame-receiver", f"{brightness}", f"{orientation}", f"{PORT}"])
    p3 = subprocess.Popen(["./modules/hardware-server/hardware-server", f"{int(PORT) + 1}"])

try:
    while True:
        time.sleep(1)
        if arguments_count >= 6:
            if p1.poll() is not None or p2.poll() is not None or p3.poll() is not None:
                print("[MAIN] One process exited, shutting down the other")
                break
        else:
            if p1.poll() is not None:
                print("[MAIN] Integration runner closed")
                break
except Exception as e:
    print(f"[MAIN] {e}")
    print("[MAIN] Stopping")
    p1.terminate()
    if arguments_count >= 6:
        p2.send_signal(signal.CTRL_BREAK_EVENT)
        p3.terminate()