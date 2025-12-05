from PIL import Image
import subprocess
import threading
import win32gui
import win32con
import pystray
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
tray = 0
PORT = 54217

argumentsCount = len(sys.argv)
minimum = False
stopRequested = False
hideOnce = False
program = win32gui.GetForegroundWindow()

def notEnoughArguments():
    print("[MAIN] Not enough arguments provided")
    print("[MAIN] Usage: liquidWeb configuration (0-1) url fps (0-30) brightness (0-100%) orientation (0-360°) system-tray (0-1) port (Optional. Will use the selected one plus two next ones. Default 54217,54218,54219)")
    sys.exit()

def trayQuit(icon, item):
    global stopRequested
    stopRequested = True
    icon.stop()

def show(icon, item):
    win32gui.ShowWindow(program, win32con.SW_RESTORE)

def trayThread():
    img = Image.new("RGB", (16, 16), (80, 0, 121))
    icon = pystray.Icon(name="liquidWeb-cli", title="liquidWeb", icon=img, menu=pystray.Menu(
        pystray.MenuItem("Show", show),
        pystray.MenuItem("Quit", trayQuit)
    ))
    icon.run()

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
    tray = sys.argv[6]
if argumentsCount >= 8:
    PORT = sys.argv[7]

if argumentsCount == 3:
    width = 1280
    height = 720
    fps = 60
else:
    width = 640
    height = 640
    configuration = 0

p1 = subprocess.Popen(["./modules/integration-runner-win32-x64/integration-runner.exe", f"--width={width}", f"--height={height}", f"--fps={fps}", f"--configuration={configuration}", f"--url={url}", f"--port={PORT}"])
if argumentsCount >= 5:
    p2 = subprocess.Popen(["./modules/frame-receiver", f"{brightness}", f"{orientation}", f"{PORT}"])
    p3 = subprocess.Popen(["./modules/hardware-server/hardware-server", f"{int(PORT) + 1}"])

if tray == "1":
    threading.Thread(target=trayThread, daemon=True).start()

try:
    while True:
        time.sleep(1)
        if tray == "1" and not hideOnce:
            win32gui.ShowWindow(program , win32con.SW_HIDE)
            hideOnce = True
        if tray == "1" and hideOnce:
            placement = win32gui.GetWindowPlacement(program)
            if placement[1] == win32con.SW_SHOWMINIMIZED:
                win32gui.ShowWindow(program , win32con.SW_HIDE)
        if stopRequested:
            win32gui.ShowWindow(program, win32con.SW_RESTORE)
            p1.terminate()
            p2.send_signal(signal.CTRL_BREAK_EVENT)
            p3.terminate()
            print("[MAIN] Requested quit from tray icon")
            break
        if argumentsCount >= 6:
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
    if argumentsCount >= 6:
        p2.send_signal(signal.CTRL_BREAK_EVENT)
        p3.terminate()