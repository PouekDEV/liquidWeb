from util import normalize_profile, interpolate_profile, clamp
from collections import namedtuple
from PIL import Image, ImageDraw
from enum import Enum, IntEnum
from typing import Tuple
from io import BytesIO
import q565_rust
import usb.core
import usb.util
import time
import math
import hid

_NZXT_VID = 0x1E71
_DEFAULT_TIMEOUT_MS = 1000
_HID_WRITE_LENGTH = 64
_HID_READ_LENGTH = 64
_MAX_READ_UNTIL_RETRIES = 50
_CRITICAL_TEMPERATURE = 59
_COMMON_WRITE_HEADER = [
    0x12,
    0xFA,
    0x01,
    0xE8,
    0xAB,
    0xCD,
    0xEF,
    0x98,
    0x76,
    0x54,
    0x32,
    0x10,
]

Resolution = namedtuple("Resolution", ["width", "height"])

class RENDERING_MODE(str, Enum):
    RGBA = "RGBA"
    GIF = "GIF"
    FAST_GIF = "FAST_GIF"
    Q565 = "Q565"

class DISPLAY_MODE(IntEnum):
    LIQUID = 2
    BUCKET = 4
    FAST_BUCKET = 5

SUPPORTED_DEVICES = [
    {
        "pid": 0x3008,
        "name": "Kraken Z3",
        "resolution": Resolution(320, 320),
        "renderingMode": RENDERING_MODE.RGBA,
        "totalBuckets": 16,
        "maxBucketSize": 20 * 1024 * 1024,  # 20MB
        "supportsLiquidMode": True,
        "speedChannels": {
            "pump": ([0x1, 0x0, 0x0], 20, 100),
            "fan": ([0x2, 0x0, 0x0], 0, 100),
        }
    },
    {
        "pid": 0x300C,
        "name": "Kraken Elite",
        "resolution": Resolution(640, 640),
        "renderingMode": RENDERING_MODE.Q565,
        "totalBuckets": 16,
        "maxBucketSize": 20 * 1024 * 1024,  # 20MB
        "supportsLiquidMode": True,
        "speedChannels": {
            "pump": ([0x1, 0x1, 0x0], 20, 100),
            "fan": ([0x2, 0x1, 0x1], 0, 100),
        }
    },
    {
        "pid": 0x3012,
        "name": "Kraken Elite v2",
        "resolution": Resolution(640, 640),
        "renderingMode": RENDERING_MODE.Q565,
        "totalBuckets": 16,
        "maxBucketSize": 20 * 1024 * 1024,  # 20MB
        "supportsLiquidMode": True,
        "speedChannels": {
            "pump": ([0x1, 0x1, 0x0], 20, 100),
            "fan": ([0x2, 0x1, 0x1], 0, 100),
        }
    }
]

class KrakenLCD:
    pid: int
    serial: str
    name: str
    resolution: Resolution
    total_buckets: int
    max_bucket_size: int
    max_RGBA_bucket_size: int
    supports_liquid_mode: bool
    rendering_mode: RENDERING_MODE
    last_read_message: bytes
    stream_ready = False
    next_frame_bucket = 0
    buckets_to_use = 2
    black: Image.Image
    mask: Image.Image
    cache = None

    def __init__(self, brightness, orientation):
        for dev in SUPPORTED_DEVICES:
            info = hid.enumerate(_NZXT_VID, dev["pid"])
            if len(info) > 0:
                self.hid_info = info[0]
                self.name = dev["name"]
                self.pid = dev["pid"]
                self.resolution: Resolution = dev["resolution"]
                self.rendering_mode = dev["renderingMode"]
                self.total_buckets = dev["totalBuckets"]
                self.supports_liquid_mode = dev["supportsLiquidMode"]
                self.max_bucket_size = dev["maxBucketSize"]
                self.max_RGBA_bucket_size: int = min(
                    dev["maxBucketSize"],
                    (self.resolution.width * self.resolution.height * 4),
                )
                self.buckets_to_use = max(self.total_buckets, 2)
                self.brightness = brightness
                self.orientation = orientation
                self.speed_channels = dev["speedChannels"]
                print(f"[DRIVER] Detected {self.name} (PID: {self.pid})")
                break
        else:
            raise Exception("No supported device found")

        try:
            self.serial = self.hid_info["serial_number"]
            self.hid_dev = hid.device()
            self.hid_dev.open_path(self.hid_info["path"])
            devices = usb.core.find(find_all=True, idVendor=_NZXT_VID, idProduct=self.pid)
            self.bulk_dev = None
            for dev in devices:
                try:
                    serial = usb.util.get_string(dev, dev.iSerialNumber)
                    if self.hid_info["serial_number"] in serial:
                        self.bulk_dev = dev
                        if self.bulk_dev.is_kernel_driver_active(0):
                            self.bulk_dev.detach_kernel_driver(0)
                        self.bulk_dev.set_configuration()
                        break
                except Exception as e:
                    continue
            if self.bulk_dev is None:
                raise ValueError("Device not found or serial number mismatch.")
        except Exception:
            # https://github.com/liquidctl/liquidctl/blob/main/extra/linux/71-liquidctl.rules
            raise Exception("Could not connect to kraken device. Do you have the required permissions?")

        self.black = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
        self.mask = Image.new("RGBA", self.resolution, (0, 0, 0, 0))
        mask_canvas = ImageDraw.Draw(self.mask)
        mask_canvas.ellipse([(0, 0), self.resolution], fill=(255, 255, 255, 255))

        self.write([0x36, 0x3])
        self.set_brightness(self.brightness)

    def get_info(self):
        return {
            "serial": self.serial,
            "name": self.name,
            "resolution": {
                "width": self.resolution.width,
                "height": self.resolution.height,
            },
            "renderingMode": self.rendering_mode
        }

    def read(self, length=_HID_READ_LENGTH, timeout=_DEFAULT_TIMEOUT_MS):
        self.hid_dev.set_nonblocking(False)
        self.last_read_message = self.hid_dev.read(max_length=length, timeout_ms=timeout)
        if timeout and not self.last_read_message:
            raise Exception("Read timeout")
        return self.last_read_message

    def clear(self):
        if self.hid_dev.set_nonblocking(True) == 0:
            timeout_ms = 0
        else:
            timeout_ms = 1
        discarded = 0
        while self.hid_dev.read(max_length=64, timeout_ms=timeout_ms):
            discarded += 1

    def read_until(self, parsers):
        for _ in range(_MAX_READ_UNTIL_RETRIES):
            msg = self.read()
            prefix = bytes(msg[0:2])
            func = parsers.pop(prefix, None)
            if func:
                return func(msg)
            if not parsers:
                return
        assert (
            False
        ), f"missing messages (attempts={_MAX_READ_UNTIL_RETRIES}, missing={len(parsers)})"

    def write(self, data) -> int:
        self.hid_dev.set_nonblocking(False)
        padding = [0x0] * (_HID_WRITE_LENGTH - len(data))
        res = self.hid_dev.write(data + padding)
        if res < 0:
            raise OSError("Could not write to device")
        return res

    def bulk_write(self, data: bytes) -> None:
        self.bulk_dev.write(0x2, data)

    def parse_standard_result(self, packet) -> bool:
        return packet[14] == 1

    def format_standard_result(
        self, op: str, bucket: int, status: bool, tentative: int = -1
    ) -> str:
        result_message = (
            "Success" if status else "Fail[{}]".format(self.last_read_message[14])
        )
        tentative_text = "[{}]".format(tentative)
        return "{:20} bucket {:2}: {}".format(
            op + (tentative_text if (tentative > 0) else ""),
            bucket,
            result_message,
        )

    def parse_stats(self, packet):
        return {"liquid": packet[15] + packet[16] / 10, "pump_duty": packet[19], "pump_speed": packet[18] << 8 | packet[17], "fan_speed": packet[24] << 8 | packet[23], "fan_duty": packet[25]}

    def get_stats(self):
        self.write([0x74, 0x1])
        return self.read_until({b"\x75\x01": self.parse_stats})

    def set_brightness(self, brightness: int) -> None:
        self.write(
            [
                0x30,
                0x02,
                0x01,
                max(0, min(100, brightness)),
                0x0,
                0x0,
                0x1,
                0x3,  # default orientation,
            ]
        )

    # Taken from liquidctl
    def set_fixed_speed(self, channel, duty):
        cid, dmin, dmax = self.speed_channels[channel]
        header = [0x72] + cid
        norm = normalize_profile([(0, duty), (_CRITICAL_TEMPERATURE - 1, duty)], _CRITICAL_TEMPERATURE)
        stdtemps = list(range(0, _CRITICAL_TEMPERATURE + 1))
        interp = [clamp(interpolate_profile(norm, t), dmin, dmax) for t in stdtemps]
        self.write(header + interp)

    def set_lcd_mode(self, mode: DISPLAY_MODE, bucket=0) -> bool:
        self.write([0x38, 0x1, mode, bucket])
        return self.read_until({b"\x39\x01": self.parse_standard_result})

    def delete_bucket(self, bucket: int, retries=1) -> bool:
        status = False
        for i in range(retries):
            self.write([0x32, 0x2, bucket])
            status = self.read_until({b"\x33\x02": self.parse_standard_result})
            if status:
                return True
        else:
            return False

    def delete_all_buckets(self):
        for bucket in range(self.total_buckets):
            for i in range(10):
                status = self.delete_bucket(bucket, i)
                if status:
                    break
                time.sleep(0.1)
            else:
                raise Exception("Could not delete bucket {}".format(bucket))

    def create_bucket(
        self,
        bucket: int,
        address: Tuple[int, int] = [0, 0],
        size: int = None,
    ):
        size_bytes = list(
            math.ceil((size or self.max_RGBA_bucket_size) / 1024 + 1).to_bytes(2, "little")
        )
        self.write(
            [
                0x32,
                0x01,
                bucket,
                bucket + 1,
                address[0],
                address[1],
                size_bytes[0],
                size_bytes[1],
                0x01,
            ]
        )
        status = self.read_until({b"\x33\x01": self.parse_standard_result})
        return status

    def write_RGBA(self, RGBA_data: bytes, bucket: int) -> bool:
        self.write([0x36, 0x01, bucket])
        status = self.read_until({b"\x37\x01": self.parse_standard_result})
        if not status:
            return False

        header = (
            _COMMON_WRITE_HEADER
            + [
                0x02,
                0x00,
                0x00,
                0x00,
            ]
            + list(len(RGBA_data).to_bytes(4, "little"))
        )

        self.bulk_write(bytes(header))
        self.bulk_write(RGBA_data)

        self.write([0x36, 0x02, bucket])
        status = self.read_until({b"\x37\x02": self.parse_standard_result})
        return status

    def write_GIF(self, gif_data: bytes, bucket: int) -> bool:
        self.write([0x36, 0x01, 0x0, 0x0])
        status = self.read_until({b"\x37\x01": self.parse_standard_result})
        if not status:
            return False

        header = (
            _COMMON_WRITE_HEADER
            + [
                0x01,
                0x00,
                0x00,
                0x00,
            ]
            + list(len(gif_data).to_bytes(4, "little"))
        )

        self.bulk_write(bytes(header))

        self.bulk_write(gif_data)

        self.write([0x36, 0x02, bucket])
        status = self.read_until({b"\x37\x02": self.parse_standard_result})
        return status

    def write_Q565(self, gif_data: bytes) -> bool:
        # 4th byte set as 1 writes to some sort of fast memory in kraken elite (bucket number is not relevant)
        self.write([0x36, 0x01, 0x0, 0x1, 0x8])
        status = self.read_until({b"\x37\x01": self.parse_standard_result})
        if not status:
            return False

        header = (
            _COMMON_WRITE_HEADER
            + [
                0x08,
                0x00,
                0x00,
                0x00,
            ]
            + list(len(gif_data).to_bytes(4, "little"))
        )

        self.bulk_write(bytes(header))

        self.bulk_write(gif_data)

        self.write([0x36, 0x02])
        status = self.read_until({b"\x37\x02": self.parse_standard_result})
        return status

    def write_frame(self, frame: bytes):
        if not self.stream_ready:
            return False
        self.clear()
        result = False
        if self.rendering_mode == RENDERING_MODE.RGBA:
            result = self.write_RGBA(frame, self.next_frame_bucket) and self.set_lcd_mode(
                DISPLAY_MODE.BUCKET, self.next_frame_bucket
            )
        if self.rendering_mode == RENDERING_MODE.GIF:
            start_address = list(
                math.ceil(
                    self.next_frame_bucket * ((self.max_RGBA_bucket_size) / 1024 + 1)
                ).to_bytes(2, "little")
            )
            result = (
                (
                    self.delete_bucket(self.next_frame_bucket)
                    or self.delete_bucket(self.next_frame_bucket)
                )
                and self.create_bucket(self.next_frame_bucket, start_address)
                and self.write_GIF(frame, self.next_frame_bucket)
                and self.set_lcd_mode(DISPLAY_MODE.BUCKET, self.next_frame_bucket)
            )
        if self.rendering_mode == RENDERING_MODE.Q565:
            result = self.write_Q565(frame)
        self.next_frame_bucket = (self.next_frame_bucket + 1) % self.buckets_to_use
        return result

    def image_to_frame(self, img: Image.Image, adaptive=False) -> bytes:
        img = img.resize(self.resolution).rotate(self.orientation)
        # cut the image to circular frame. This reduce gif size by ~20%
        img = Image.composite(img, self.black, self.mask)

        if self.rendering_mode == RENDERING_MODE.RGBA:
            raw = list(img.convert("RGB").getdata())
            output = []
            for i in range(img.size[0] * img.size[1]):
                output.append(raw[i][0])
                output.append(raw[i][1])
                output.append(raw[i][2])
                output.append(0)
            return bytes(output)
        elif self.rendering_mode == RENDERING_MODE.Q565:
            img = img.convert("RGB")
            width, height = img.size
            img_bytes = img.tobytes()
            return q565_rust.py_encode(
                width, height, img_bytes
            )
        else:
            byteio = BytesIO()

            def convert():
                nonlocal img
                if adaptive:
                    img = img.convert("RGB").convert(
                        "P", palette=Image.Palette.ADAPTIVE, colors=64
                    )
                else:
                    img = img.convert("RGB").convert("P")
                img.save(byteio, "GIF", interlace=False, optimize=True)

            convert()
            return byteio.getvalue()

    def setup_stream(self):
        if self.supports_liquid_mode:
            self.set_lcd_mode(DISPLAY_MODE.LIQUID, 0x0)
            time.sleep(0.1)

        if self.rendering_mode == RENDERING_MODE.RGBA:
            self.delete_all_buckets()
            for i in range(self.buckets_to_use):
                start_address = list(
                    math.ceil(i * ((self.max_RGBA_bucket_size) / 1024 + 1)).to_bytes(
                        2, "little"
                    )
                )
                self.create_bucket(i, start_address)

        self.set_lcd_mode(DISPLAY_MODE.BUCKET, 0x0)
        self.stream_ready = True