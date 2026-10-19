"""CPython check of the datasheet properties: the buggy driver must break one, the fixed one must not."""
import importlib.util
import struct
import sys
import types
from pathlib import Path

root = Path(sys.argv[1])
for name in ("adafruit_bus_device", "adafruit_bus_device.i2c_device", "adafruit_bus_device.spi_device", "micropython"):
    m = types.ModuleType(name); sys.modules[name] = m
sys.modules["adafruit_bus_device"].i2c_device = sys.modules["adafruit_bus_device.i2c_device"]
sys.modules["adafruit_bus_device.i2c_device"].I2CDevice = object
sys.modules["adafruit_bus_device.spi_device"].SPIDevice = object
sys.modules["micropython"].const = lambda x: x
busio = types.ModuleType("busio"); busio.I2C = busio.SPI = object; sys.modules["busio"] = busio

def load(path):
    spec = importlib.util.spec_from_file_location(path.stem + path.parent.name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

class Dev:
    def __init__(self, data): self.data = data
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def readinto(self, buf, **kw): buf[:len(self.data)] = self.data

GRID = sorted(set(range(0, 65536, 157)) | {0, 1, 36862, 36863, 36864, 65534, 65535})

def shtc3(mod):
    mod.time.sleep = lambda s: None
    bad = 0
    for st in range(1873, 63664):
        o = mod.SHTC3.__new__(mod.SHTC3)
        o._buffer = bytearray(6); o.low_power = False; o._write_command = lambda c: None; o._cached_sleep = False
        t = bytes([st >> 8, st & 0xFF]); h = bytes([0, 0])
        o.i2c_device = Dev(t + bytes([o._crc8(t)]) + h + bytes([o._crc8(h)]))
        temp, _ = o.measurements
        bad += not (-40 <= temp <= 125)
    return bad

def max31855(mod):
    bad = 0
    for refer in range(-640, 2001):
        o = mod.MAX31855.__new__(mod.MAX31855)
        o.data = bytearray(4); o.spi_device = Dev(struct.pack(">hh", 100 << 2, refer << 4))
        bad += not (-40 <= o.reference_temperature <= 125)
    return bad

def tsl(mod, prop):
    cls = mod.TSL2591
    bad = 0
    for c0 in GRID:
        for c1 in GRID:
            if prop == "visible" and c1 > c0:
                continue
            sub = type("T", (cls,), {"raw_luminosity": property(lambda self, v=(c0, c1): v)})
            o = sub.__new__(sub); o._integration_time = 0; o._gain = 0
            try:
                v = getattr(o, prop)
            except RuntimeError:
                continue
            ok = (c0 < 36863 and c1 < 36863) if prop == "lux" else (0 <= v <= 65535)
            bad += not ok
    return bad

checks = {"ada_shtc3_5": shtc3, "ada_max31855_11": max31855,
          "ada_tsl2591_6": lambda m: tsl(m, "lux"), "ada_tsl2591_34": lambda m: tsl(m, "visible")}
for key, fn in checks.items():
    b = fn(load(root / "arquivo_com_bug" / f"{key}.py")); f = fn(load(root / "arquivo_corrigido" / f"{key}.py"))
    print(f"{key:16s} violações com bug={b:6d}  corrigida={f}  {'OK' if b and not f else 'PROBLEMA'}")
