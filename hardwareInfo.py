# When fully migrating everything to Linux use psutil and hwmon

from HardwareMonitor.Hardware import *
from HardwareMonitor.Util import *
from aiohttp import web
import asyncio
import psutil
import json

PORT = 54218
formatted = {
    "cpus": [],
    "gpus": [],
    "ram": {
        "totalSize": psutil.virtual_memory().total,
        "inUse": 0,
        "modules": []
    },
    "kraken": {
        "liquidTemperature": None # This value is obtainable but we don't want to block the frameReceiver just to obtain it
    }
}
computer = OpenComputer(cpu=True, gpu=True, memory=True)

async def update_info():
    minFanSpeed = -1
    maxFanSpeed = 0
    while True:
        await asyncio.to_thread(computer.Update)
        data = ToBuiltinTypes(computer.Hardware)
        hardwareList = json.loads(json.dumps(data))
        formatted["cpus"] = []
        formatted["gpus"] = []
        for hardware in hardwareList:
            cpu = {
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
                "stockFrequency": None,
                "fanSpeed": 0,
                "minFanSpeed": minFanSpeed,
                "maxFanSpeed": maxFanSpeed,
                "tdp": None,
                "power": 0
            }
            gpu = {
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
            if "Cpu" in hardware["HardwareType"]:
                cpu["name"] = hardware["Name"]
                sensors = hardware["Sensors"]
                average = 0
                maximum = 0
                minimum = 0
                if "intel" in cpu["name"].lower():
                    cpu["manufacturer"] = "GenuineIntel"
                if "amd" in cpu["name"].lower():
                    cpu["manufacturer"] = "AuthenticAMD"
                for sensor in sensors:
                    try:
                        if sensor["Name"] == "CPU Total":
                            cpu["load"] = sensor["Value"]
                        if sensor["SensorType"] == "Load" and "CPU Core #" in sensor["Name"] and "Thread #2" not in sensor["Name"]:
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
                            val = sensor["Value"]
                            average += val
                            if val > maximum:
                                maximum = val
                            if val < minimum:
                                minimum = val
                    except KeyError:
                        continue
                if cpu["numCores"]:
                    average /= cpu["numCores"]
                cpu["frequency"] = average
                cpu["numThreads"] += cpu["numCores"]
                fanSpeed = -1 # This should be replaced on Linux if it's going to be available
                cpu["fanSpeed"] = fanSpeed
                if fanSpeed > maxFanSpeed:
                    maxFanSpeed = fanSpeed
                if minFanSpeed == -1 or fanSpeed < minFanSpeed:
                    minFanSpeed = fanSpeed
                cpu["minFanSpeed"] = minFanSpeed
                cpu["maxFanSpeed"] = maxFanSpeed
                formatted["cpus"].append(cpu)
            if "Gpu" in hardware["HardwareType"]:
                gpu["name"] = hardware["Name"]
                sensors = hardware["Sensors"]
                for sensor in sensors:
                    try:
                        t = sensor["SensorType"]
                        n = sensor["Name"]
                        if t == "Load" and n == "GPU Core":
                            gpu["load"] = sensor["Value"]
                        if t == "Temperature" and n == "GPU Core":
                            gpu["temperature"] = sensor["Value"]
                            gpu["minTemperature"] = sensor["Min"]
                            gpu["maxTemperature"] = sensor["Max"]
                        if t == "Clock" and n == "GPU Core":
                            gpu["frequency"] = sensor["Value"]
                            gpu["minFrequency"] = sensor["Min"]
                            gpu["maxFrequency"] = sensor["Max"]
                        if t == "Fan" and n == "GPU Fan 1":
                            gpu["fanSpeed"] = sensor["Value"]
                            gpu["minFanSpeed"] = sensor["Min"]
                            gpu["maxFanSpeed"] = sensor["Max"]
                        if t == "Power" and n == "GPU Package":
                            gpu["power"] = sensor["Value"]
                    except KeyError:
                        continue
                formatted["gpus"].append(gpu)
        formatted["gpus"].reverse()
        formatted["ram"]["inUse"] = psutil.virtual_memory().used
        await asyncio.sleep(1)

async def http_handler(_request):
    return web.json_response(formatted)

async def run_server():
    app = web.Application()
    app.router.add_get("/", http_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    print(f"Serving hardware info on http://127.0.0.1:{PORT}")

async def run():
    asyncio.create_task(update_info())
    await run_server()
    await asyncio.Future()

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()