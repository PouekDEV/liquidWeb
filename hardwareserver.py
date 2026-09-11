from util import normalize_profile, interpolate_profile, cpu_vendor_and_model_name, intel_integrated_graphics_present, is_nvidia_present, get_intel_integrated_graphics_name
from driver import _CRITICAL_TEMPERATURE
from aioxmlrpc.client import ServerProxy
from aiohttp import web
from pynvml import *
import asyncio
import psutil
import math
import json
import copy
import sys

PORT = 54218
_CRITICAL_TEMPERATURE_CPU = 99

if not is_nvidia_present():
    raise Exception("No NVIDIA GPU detected")
else:
    nvmlInit()

intel_integrated = intel_integrated_graphics_present()

formatted = {
    "cpus": [
        {
            "name": cpu_vendor_and_model_name()[1],
            "manufacturer": cpu_vendor_and_model_name()[0],
            "codeName": None,
            "socket": None,
            "load": psutil.cpu_percent() / 100,
            "numCores": psutil.cpu_count(logical=False),
            "numThreads": psutil.cpu_count(),
            "temperature": 0,
            "minTemperature": 0,
            "maxTemperature": 0,
            "frequency": psutil.cpu_freq()[0],
            "minFrequency": psutil.cpu_freq()[1],
            "maxFrequency": psutil.cpu_freq()[2],
            "stockFrequency": None,
            "fanSpeed": 0, # can't get this data from psutil since kraken's handle is taken while frame writer is running
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
        "liquidTemperature": 0 # same thing as above
    }
}
lcd = None
config = {"fan": [], "pump": [], "fan_sensor": "", "pump_sensor": "", "cpu": 0, "gpu": 0, "cpu_temp_chip": ""}
duty_sensors = ["cpu", "gpu", "liquid"]
file_path = "/var/lib/liquidWeb"
cpu_temps = [0] * 4
last_updated_duty = {
    "fan": 0,
    "pump": 0
}
# For parity with Windows we don't get any data for this GPU
gpu = {
    "name": f"Intel(R) {get_intel_integrated_graphics_name()}",
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
if intel_integrated:
    formatted["gpus"].append(copy.copy(gpu))
gpu["minFanSpeed"] = -1
formatted["gpus"].append(gpu)

async def update_kraken():
    while True:
        # This is a very latency expensive option that's why we do it every 10 seconds
        try:
            stats = await lcd.get_stats()
            formatted["kraken"]["liquidTemperature"] = stats["liquid"]
            formatted["cpus"][0]["fanSpeed"] = stats["fan_speed"]
        except Exception:
            pass
        await asyncio.sleep(10)

async def update_info():
    while True:
        # Nobody has more than one CPU right?
        formatted["cpus"][0]["load"] = psutil.cpu_percent() / 100
        try:
            sensors = psutil.sensors_temperatures()[config["cpu_temp_chip"]]
            sum = 0
            for core in sensors:
                sum += core.current
            average = sum / len(sensors)
            formatted["cpus"][0]["temperature"] = average
        except KeyError:
            pass
        if formatted["cpus"][0]["temperature"] < formatted["cpus"][0]["minTemperature"] or formatted["cpus"][0]["minTemperature"] == 0:
            formatted["cpus"][0]["minTemperature"] = formatted["cpus"][0]["temperature"]
        if formatted["cpus"][0]["temperature"] > formatted["cpus"][0]["maxTemperature"]:
            formatted["cpus"][0]["maxTemperature"] = formatted["cpus"][0]["temperature"]
        if formatted["cpus"][0]["fanSpeed"] < formatted["cpus"][0]["minFanSpeed"] or formatted["cpus"][0]["minFanSpeed"] == 0:
            formatted["cpus"][0]["minFanSpeed"] = formatted["cpus"][0]["fanSpeed"]
        if formatted["cpus"][0]["fanSpeed"] > formatted["cpus"][0]["maxFanSpeed"]:
            formatted["cpus"][0]["maxFanSpeed"] = formatted["cpus"][0]["fanSpeed"]
        formatted["cpus"][0]["frequency"] = psutil.cpu_freq()[0]
        formatted["cpus"][0]["minFrequency"] = psutil.cpu_freq()[1]
        formatted["cpus"][0]["maxFrequency"] = psutil.cpu_freq()[2]
        order = 0
        if intel_integrated:
            order = 1
        # We don't check for more than one GPU
        handle = nvmlDeviceGetHandleByIndex(0)
        formatted["gpus"][order]["name"] = nvmlDeviceGetName(handle)
        formatted["gpus"][order]["load"] = float(nvmlDeviceGetUtilizationRates(handle).gpu)
        formatted["gpus"][order]["temperature"] = float(nvmlDeviceGetTemperatureV(handle, 0))
        if formatted["gpus"][order]["temperature"] < formatted["gpus"][order]["minTemperature"] or formatted["gpus"][order]["minTemperature"] == 0:
            formatted["gpus"][order]["minTemperature"] = formatted["gpus"][order]["temperature"]
        if formatted["gpus"][order]["temperature"] > formatted["gpus"][order]["maxTemperature"]:
            formatted["gpus"][order]["maxTemperature"] = formatted["gpus"][order]["temperature"]
        clocks = nvmlDeviceGetCurrentClockFreqs(handle)
        formatted["gpus"][order]["frequency"] = float(clocks.split(",")[0].split("=")[1])
        formatted["gpus"][order]["minFrequency"] = float(clocks.split(",")[1].split("=")[1])
        formatted["gpus"][order]["maxFrequency"] = float(clocks.split(",")[2].split("=")[1])
        try:
            fans = nvmlDeviceGetFanSpeedRPM(handle)
            formatted["gpus"][order]["fanSpeed"] = fans
            if formatted["gpus"][order]["fanSpeed"] < formatted["gpus"][order]["minFanSpeed"] or formatted["gpus"][order]["minFanSpeed"] == -1:
                formatted["gpus"][order]["minFanSpeed"] = formatted["gpus"][order]["fanSpeed"]
            if formatted["gpus"][order]["fanSpeed"] > formatted["gpus"][order]["maxFanSpeed"]:
                formatted["gpus"][order]["maxFanSpeed"] = formatted["gpus"][order]["fanSpeed"]
        except NVMLError:
            pass
        try:
            power = nvmlDeviceGetPowerUsage(handle) / 1000
        except NVMLError:
            power = 0
        formatted["gpus"][order]["power"] = power
        formatted["ram"]["inUse"] = psutil.virtual_memory().used / 1024 / 1024
        await check_curves(formatted["cpus"][config["cpu"]]["temperature"], formatted["gpus"][config["gpu"]]["temperature"], formatted["kraken"]["liquidTemperature"])
        await asyncio.sleep(1)

# Modified from liquidctl yoda
async def update_duty(channel, temp, critical_temp):
    global config
    norm = normalize_profile(config[channel], critical_temp)
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
    duty = interpolate_profile(norm, ema)
    if last_updated_duty[channel] != duty:
        last_updated_duty[channel] = duty
        print(f"[HARDWARE-SERVER] Setting {channel} duty to {duty}% | {temp}°C")
        try:
            await lcd.set_fixed_speed(channel, duty)
        except Exception:
            print(f"[HARDWARE-SERVER] There was an error while writing duty info for {channel}")

async def check_curves(cpu_temp, gpu_temp, liquid_temp):
    global config, cpu_temps
    await asyncio.sleep(1)
    cpu_temps.append(cpu_temp)
    cpu_temps.pop(0)
    average_cpu_temp = 0
    for temp in cpu_temps:
        average_cpu_temp += temp
    average_cpu_temp /= len(cpu_temps)
    if len(config["fan"]) > 0 and config["fan_sensor"] in duty_sensors:
        if config["fan_sensor"] == duty_sensors[0]:
            temp = average_cpu_temp
        if config["fan_sensor"] == duty_sensors[1]:
            temp = gpu_temp
        if config["fan_sensor"] == duty_sensors[2]:
            temp = liquid_temp
        await update_duty("fan", temp, _CRITICAL_TEMPERATURE_CPU)
    if len(config["pump"]) > 0 and config["pump_sensor"] in duty_sensors:
        if config["pump_sensor"] == duty_sensors[0]:
            temp = average_cpu_temp
        if config["pump_sensor"] == duty_sensors[1]:
            temp = gpu_temp
        if config["pump_sensor"] == duty_sensors[2]:
            temp = liquid_temp
        await update_duty("pump", temp, _CRITICAL_TEMPERATURE)

async def http_handler(_request):
    return web.json_response(formatted)

async def run_server():
    app = web.Application()
    app.router.add_get("/", http_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    print(f"[HARDWARE-SERVER] Serving hardware info on http://localhost:{PORT}")

async def run():
    global lcd
    asyncio.create_task(update_info())
    asyncio.create_task(update_kraken())
    lcd = ServerProxy(f"http://localhost:{PORT + 1}", timeout=None)
    print(f"[HARDWARE-SERVER] Grabbing device handle from port {PORT + 1}")
    await run_server()
    await asyncio.Future()

def main():
    global config
    try:
        with open(f"{file_path}/curves.json", "r") as f:
            try:
                config = json.loads(f.read())
                if len(config["fan"]) % 2 == 0:
                    tuple_pointer = 0
                    fan = []
                    while tuple_pointer < len(config["fan"]):
                        fan.append((config["fan"][tuple_pointer], config["fan"][tuple_pointer + 1]))
                        tuple_pointer += 2
                    config["fan"] = fan
                else:
                    config["fan"] = []
                    raise KeyError
                if len(config["pump"]) % 2 == 0:
                    tuple_pointer = 0
                    pump = []
                    while tuple_pointer < len(config["pump"]):
                        pump.append((config["pump"][tuple_pointer], config["pump"][tuple_pointer + 1]))
                        tuple_pointer += 2
                    config["pump"] = pump
                else:
                    config["pump"] = []
                    raise KeyError
                print("[HARDWARE-SERVER] Loaded custom curve config")
            except KeyError:
                print("[HARDWARE-SERVER] There was an error while parsing curve config")
    except FileNotFoundError:
        with open(f"{file_path}/curves.json", "w") as f:
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