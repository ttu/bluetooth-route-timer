"""Bluetooth scanner module for discovering and connecting to BLE sensors."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


@dataclass
class DeviceReading:
    """Represents a single Bluetooth device reading.

    Args:
        device: The Bluetooth device that was detected
        timestamp: When the device was detected
        rssi: Signal strength in dBm
    """

    device: BLEDevice
    timestamp: datetime
    rssi: float


class BluetoothScanner:
    def __init__(self):
        self._scanner: BleakScanner | None = None
        self._device_queue: asyncio.Queue[DeviceReading] = asyncio.Queue()

    async def scan_devices(self) -> AsyncGenerator[DeviceReading, None]:
        """Scan for BLE devices and yield them as they are discovered.
        Continues scanning until stop_scan() is called.

        Yields:
            DeviceReading objects as devices are discovered.
        """

        async def _device_found(device: BLEDevice, advertisement_data: AdvertisementData) -> None:
            reading = DeviceReading(device=device, timestamp=datetime.now(), rssi=advertisement_data.rssi)
            await self._device_queue.put(reading)

        self._scanner = BleakScanner(detection_callback=_device_found, cb=dict(use_bdaddr=True))
        await self._scanner.start()

        try:
            while True:
                try:
                    # Wait for new devices with a timeout
                    reading = await asyncio.wait_for(self._device_queue.get(), timeout=0.1)
                    yield reading
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            await self.stop_scan()

    async def stop_scan(self) -> None:
        """Stop the ongoing Bluetooth scan."""
        if self._scanner:
            await self._scanner.stop()
            self._scanner = None

    async def clear_devices(self) -> None:
        """Clear the device queue."""
        await self.stop_scan()
        # Clear the queue
        while not self._device_queue.empty():
            try:
                self._device_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
