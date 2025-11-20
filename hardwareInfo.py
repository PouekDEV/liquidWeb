from http.server import BaseHTTPRequestHandler, HTTPServer
from HardwareMonitor.Hardware import *
from HardwareMonitor.Util import *
from threading import Thread
from time import sleep
import json

PORT = 54218
formatted = {
    "cpus": [],
    "gpus": [],
    "ram": {
        "totalSize": 0,
        "inUse": 0,
        "modules": []
    },
    "kraken": {
        "liquidTemperature": 0
    }
}
computer = OpenComputer(cpu=True, gpu=True, memory=True)

class InfoUpdater(Thread):
    def __init__(self, computer, formatted):
        Thread.__init__(self, name="InfoUpdater")
        self.daemon = True
        self.computer = computer
        self.formatted = formatted
        self.minFanSpeed = 0
        self.maxFanSpeed = 0
        self.cpuTemp = {
            "name": "",
            "manufacturer": "",
            "codeName": None,
            "socket": None,
            "load": 0,
            "numCores": 0,
            "numThreads": 0,
            "temperature": 0,
            "minTemperature": 0,
            "maxTemperature": 0,
            "frequency": 0,
            "minFrequency": 0,
            "maxFrequency": 0,
            "stockFrequency":  None,
            "fanSpeed": 0,
            "minFanSpeed": 0,
            "maxFanSpeed": 0,
            "tdp": None,
            "power": 0
        }
        self.gpuTemp = {
            "name": "",
            "load": 0,
            "temperature": 0,
            "minTemperature": 0,
            "maxTemperature": 0,
            "frequency": 0,
            "minFrequency": 0,
            "maxFrequency": 0,
            "stockFrequency": None,
            "fanSpeed": 0,
            "minFanSpeed": 0,
            "maxFanSpeed": 0,
            "power": 0
        }
    def run(self):
        while True:
            sleep(1)
            self.computer.Update()
            data = ToBuiltinTypes(self.computer.Hardware)
            hardwareList = json.loads(json.dumps(data))
            self.formatted["cpus"] = []
            self.formatted["gpus"] = []
            for hardware in hardwareList:
                cpu = self.cpuTemp.copy()
                gpu = self.gpuTemp.copy()
                if hardware["Name"] == "Total Memory":
                    sensors = hardware["Sensors"]
                    used = 0
                    available = 0
                    for sensor in sensors:
                        if sensor["Name"] == "Memory Used":
                            used = sensor["Value"]
                        if sensor["Name"] == "Memory Available":
                            available = sensor["Value"]
                    self.formatted["ram"]["inUse"] = used
                    self.formatted["ram"]["totalSize"] = used + available
                if "Cpu" in hardware["HardwareType"]:
                    cpu["name"] = hardware["Name"]
                    average = 0
                    max = 0
                    min = 0
                    if "intel" in cpu["name"].lower():
                        cpu["manufacturer"] = "GenuineIntel"
                    if "amd" in cpu["name"].lower():
                        cpu["manufacturer"] = "AuthenticAMD"
                    sensors = hardware["Sensors"]
                    for sensor in sensors:
                        try:
                            if sensor["Name"] == "CPU Total":
                                cpu["load"] = sensor["Value"]
                            if sensor["SensorType"] == "Load" and "CPU Core #" in sensor["Name"] and not "Thread #2" in sensor["Name"]:
                                cpu["numCores"] += 1
                            if sensor["SensorType"] == "Load" and "CPU Core" in sensor["Name"] and "Thread #1" in sensor["Name"]:
                                cpu["numThreads"] += 1
                            if sensor["SensorType"] == "Power" and sensor["Name"] == "CPU Cores":
                                cpu["power"] = sensor["Value"]
                            if sensor["SensorType"] == "Temperature" and sensor["Name"] == "Core Average":
                                cpu["temperature"] = sensor["Value"]
                                cpu["minTemperature"] = sensor["Min"]
                                cpu["maxTemperature"] = sensor["Max"]
                            if sensor["SensorType"] == "Clock":
                                value = sensor["Value"]
                                average += value
                                if value > max:
                                    max = value
                                if value < min:
                                    min = value
                        except KeyError:
                            continue
                    average = average / cpu["numCores"]
                    cpu["numThreads"] += cpu["numCores"]
                    fanSpeed = -1 # To be set from the driver
                    cpu["fanSpeed"] = fanSpeed
                    if fanSpeed > self.maxFanSpeed:
                        self.maxFanSpeed = fanSpeed
                    if fanSpeed < self.minFanSpeed:
                        self.minFanSpeed = fanSpeed
                    cpu["minFanSpeed"] = self.minFanSpeed
                    cpu["maxFanSpeed"] = self.maxFanSpeed
                    self.formatted["cpus"].append(cpu)
                if "Gpu" in hardware["HardwareType"]:
                    gpu["name"] = hardware["Name"]
                    sensors = hardware["Sensors"]
                    for sensor in sensors:
                        try:
                            if sensor["SensorType"] == "Load" and sensor["Name"] == "GPU Core":
                                gpu["load"] = sensor["Value"]
                            if sensor["SensorType"] == "Temperature" and sensor["Name"] == "GPU Core":
                                gpu["temperature"] = sensor["Value"]
                                gpu["minTemperature"] = sensor["Min"]
                                gpu["maxTemperature"] = sensor["Max"]
                            if sensor["SensorType"] == "Clock" and sensor["Name"] == "GPU Core":
                                gpu["frequency"] = sensor["Value"]
                                gpu["minFrequency"] = sensor["Min"]
                                gpu["maxFrequency"] = sensor["Max"]
                            if sensor["SensorType"] == "Fan" and sensor["Name"] == "GPU Fan 1":
                                gpu["fanSpeed"] = sensor["Value"]
                                gpu["minFanSpeed"] = sensor["Min"]
                                gpu["maxFanSpeed"] = sensor["Max"]
                            if sensor["SensorType"] == "Power" and sensor["Name"] == "GPU Package":
                                gpu["power"] = sensor["Value"]
                        except KeyError:
                            continue
                    self.formatted["gpus"].append(gpu)
            self.formatted["gpus"].reverse()
            self.formatted["kraken"]["liquidTemperature"] = -1 # To be set from the driver

class WebServer(Thread):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            value = self.server.parent.formatted
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(value).encode("utf-8"))
        def log_message(self, format, *args):
            return 
    def __init__(self, PORT, formatted):
        Thread.__init__(self, name="WebServer")
        self.daemon = True
        self.PORT = PORT
        self.formatted = formatted
    def run(self):
        server = HTTPServer(("localhost", self.PORT), self.Handler)
        server.parent = self
        print(f"Serving on http://localhost:{PORT}")
        server.serve_forever()

webServer = WebServer(PORT, formatted)
infoUpdater = InfoUpdater(computer, formatted)

webServer.start()
infoUpdater.start()

try:
    while True:
        sleep(1)
        if not (webServer.is_alive() and infoUpdater.is_alive()):
            raise KeyboardInterrupt("Some thread is dead")
except KeyboardInterrupt:
    exit()