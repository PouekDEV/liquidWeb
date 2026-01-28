from util import normalizeProfile, interpolateProfile, getCpuVendorAndModelName
from driver import _CRITICAL_TEMPERATURE
from aioxmlrpc.client import ServerProxy
from aiohttp import web
import asyncio
import psutil
import math
import json
import sys
import os

PORT = 54218
_CRITICAL_TEMPERATURE_CPU = 99
formatted = {
    "cpus": [
        {
            "name": getCpuVendorAndModelName()[1],
            "manufacturer": getCpuVendorAndModelName()[0],
            "codeName": None,
            "socket": None,
            "load": psutil.cpu_percent(interval=None) / 100,
            "numCores": psutil.cpu_count(logical=False),
            "numThreads": psutil.cpu_count(),
            "temperature": 0, #psutil.sensors_temperatures
            "minTemperature": 0,
            "maxTemperature": 0,
            "frequency": psutil.cpu_freq()[0],
            "minFrequency": psutil.cpu_freq()[1],
            "maxFrequency": psutil.cpu_freq()[2],
            "stockFrequency": None,
            "fanSpeed": 0, # lm_sensors hopefully should give the required info
            "minFanSpeed": 0,
            "maxFanSpeed": 0,
            "tdp": None,
            "power": None
        }
    ],
    "gpus": [],
    "ram": {
        "totalSize": psutil.virtual_memory().total / 1024 / 1024,
        "inUse": 0,
        "modules": []
    },
    "kraken": {
        "liquidTemperature": 0 #psutil.sensors_temperatures ?
    }
}
lcd = None
config = {"fan": [], "pump": [], "fan_sensor": "", "pump_sensor": "", "cpu": 0, "gpu": 0}
dutySensors = ["cpu", "gpu", "liquid"]
filePath = os.path.dirname(os.path.abspath(__file__))
cpuTemps = [0] * 4
lastUpdatedDuty = {
    "fan": 0,
    "pump": 0
}

async def updateInfo():
    while True:
        formatted["cpus"][0]["load"] = psutil.cpu_percent(interval=None) / 100
        formatted["cpus"][0]["frequency"] = psutil.cpu_freq()[0]
        formatted["cpus"][0]["minFrequency"] = psutil.cpu_freq()[1]
        formatted["cpus"][0]["maxFrequency"] = psutil.cpu_freq()[2]
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
        # GPUs on Linux are tricky because there is no easy common API
        # We could parse hwmon but is it really worth it?
        # Maybe stick to something like nvidia-smi to get the data
        #if "Gpu" in hardware["HardwareType"]:
        #    gpu["name"] = hardware["Name"]
        #    sensors = hardware["Sensors"]
        #    for sensor in sensors:
        #        try:
        #            t = sensor["SensorType"]
        #            n = sensor["Name"]
        #            if t == "Load" and n == "GPU Core":
        #                gpu["load"] = sensor["Value"] / 100
        #            if t == "Temperature" and n == "GPU Core":
        #                gpu["temperature"] = sensor["Value"]
        #                gpu["minTemperature"] = sensor["Min"]
        #                gpu["maxTemperature"] = sensor["Max"]
        #            if t == "Clock" and n == "GPU Core":
        #                gpu["frequency"] = sensor["Value"]
        #                gpu["minFrequency"] = sensor["Min"]
        #                gpu["maxFrequency"] = sensor["Max"]
        #            if t == "Fan" and n == "GPU Fan 1":
        #                gpu["fanSpeed"] = sensor["Value"]
        #                gpu["minFanSpeed"] = sensor["Min"]
        #                gpu["maxFanSpeed"] = sensor["Max"]
        #            if t == "Power" and n == "GPU Package":
        #                gpu["power"] = sensor["Value"]
        #        except KeyError:
        #            continue
        #    formatted["gpus"].append(gpu)
        formatted["gpus"].reverse()
        formatted["ram"]["inUse"] = psutil.virtual_memory().used / 1024 / 1024
        await checkCurves(formatted["cpus"][config["cpu"]]["temperature"], formatted["gpus"][config["gpu"]]["temperature"], formatted["kraken"]["liquidTemperature"])
        await asyncio.sleep(1)

# Modified from liquidctl yoda
async def updateDuty(channel, temp, criticalTemp):
    global config
    norm = normalizeProfile(config[channel], criticalTemp)
    average = None
    cutoff_freq = 1 / 2 / 10
    alpha = 1 - math.exp(-2 * math.pi * cutoff_freq)
    ema = average
    sample = temp
    if ema is None:
        ema = sample
    else:
        ema = alpha * sample + (1 - alpha) * ema
    average = ema
    duty = interpolateProfile(norm, ema)
    if lastUpdatedDuty[channel] != duty:
        lastUpdatedDuty[channel] = duty
        print(f"[HARDWARE-SERVER] Setting {channel} duty to {duty}% | {temp}°C")
        try:
            await lcd.setFixedSpeed(channel, duty)
        except Exception:
            print(f"[HARDWARE-SERVER] There was an error while writing duty info for {channel}")

async def checkCurves(cpuTemp, gpuTemp, liquidTemp):
    global config, cpuTemps
    await asyncio.sleep(1)
    cpuTemps.append(cpuTemp)
    cpuTemps.pop(0)
    averageCpuTemp = 0
    for temp in cpuTemps:
        averageCpuTemp += temp
    averageCpuTemp /= len(cpuTemps)
    if len(config["fan"]) > 0 and config["fan_sensor"] in dutySensors:
        if config["fan_sensor"] == dutySensors[0]:
            temp = averageCpuTemp
        if config["fan_sensor"] == dutySensors[1]:
            temp = gpuTemp
        if config["fan_sensor"] == dutySensors[2]:
            temp = liquidTemp
        await updateDuty("fan", temp, _CRITICAL_TEMPERATURE_CPU)
    if len(config["pump"]) > 0 and config["pump_sensor"] in dutySensors:
        if config["pump_sensor"] == dutySensors[0]:
            temp = averageCpuTemp
        if config["pump_sensor"] == dutySensors[1]:
            temp = gpuTemp
        if config["pump_sensor"] == dutySensors[2]:
            temp = liquidTemp
        await updateDuty("pump", temp, _CRITICAL_TEMPERATURE)

async def httpHandler(_request):
    return web.json_response(formatted)

async def runServer():
    app = web.Application()
    app.router.add_get("/", httpHandler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    print(f"[HARDWARE-SERVER] Serving hardware info on http://localhost:{PORT}")

async def run():
    global lcd
    asyncio.create_task(updateInfo())
    lcd = ServerProxy(f"http://localhost:{PORT + 1}")
    print(f"[HARDWARE-SERVER] Grabbing device handle from port {PORT + 1}")
    await runServer()
    await asyncio.Future()

def main():
    global config
    try:
        with open(f"{filePath}/curves.json", "r") as f:
            try:
                config = json.loads(f.read())
                if len(config["fan"]) % 2 == 0:
                    tuplePointer = 0
                    fan = []
                    while tuplePointer < len(config["fan"]):
                        fan.append((config["fan"][tuplePointer], config["fan"][tuplePointer + 1]))
                        tuplePointer += 2
                    config["fan"] = fan
                else:
                    config["fan"] = []
                    raise KeyError
                if len(config["pump"]) % 2 == 0:
                    tuplePointer = 0
                    pump = []
                    while tuplePointer < len(config["pump"]):
                        pump.append((config["pump"][tuplePointer], config["pump"][tuplePointer + 1]))
                        tuplePointer += 2
                    config["pump"] = pump
                else:
                    config["pump"] = []
                    raise KeyError
                print("[HARDWARE-SERVER] Loaded custom curve config")
            except KeyError:
                print("[HARDWARE-SERVER] There was an error while parsing curve config")
    except FileNotFoundError:
        with open(f"{filePath}/curves.json", "w") as f:
            f.write(json.dumps(config))
        print("[HARDWARE-SERVER] Curve config file not found. Created a blank one")
    asyncio.run(run())

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        PORT = int(sys.argv[1])
    else:
        print("[HARDWARE-SERVER] Port hasn't been provided")
        sys.exit()
    main()