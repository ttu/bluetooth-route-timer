"""Tests for the BluetoothScanner class."""

import asyncio
from datetime import datetime

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from bluetooth_route_timer.scanner import BluetoothScanner, DeviceReading


class MockBLEDevice(BLEDevice):
    """Mock BLE device that doesn't require all constructor arguments."""

    def __init__(self, address: str, name: str):
        super().__init__(
            address=address,
            name=name,
            details={},  # Empty details for testing
            rssi=0,  # Default RSSI, will be overridden in DeviceReading
        )


class MockAdvertisementData:
    """Mock advertisement data for testing."""

    def __init__(self, rssi: float):
        self.rssi = rssi


class TestBluetoothScanner:
    """Tests for the BluetoothScanner class."""

    @pytest.mark.asyncio
    async def test_known_addresses_filtering(self):
        """Test that the scanner only processes devices with known MAC addresses."""
        # Create a queue to receive device readings
        queue = asyncio.Queue()

        # Create a set of known MAC addresses
        known_addresses = {"00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"}

        # Create a scanner with known MAC addresses
        scanner = BluetoothScanner(known_addresses=known_addresses)
        scanner._device_queue = queue  # Replace the queue for testing

        # Create mock device readings
        known_device1 = MockBLEDevice("00:11:22:33:44:55", "Known Device 1")
        known_device2 = MockBLEDevice("AA:BB:CC:DD:EE:FF", "Known Device 2")
        unknown_device = MockBLEDevice("11:22:33:44:55:66", "Unknown Device")

        # Simulate device detection callbacks
        await scanner._device_found(known_device1, advertisement_data=MockAdvertisementData(rssi=-50))
        await scanner._device_found(unknown_device, advertisement_data=MockAdvertisementData(rssi=-60))
        await scanner._device_found(known_device2, advertisement_data=MockAdvertisementData(rssi=-70))

        # Check that only known devices were added to the queue
        assert queue.qsize() == 2

        # Check that the first device is the first known device
        reading1 = queue.get_nowait()
        assert reading1.device.address == "00:11:22:33:44:55"
        assert reading1.rssi == -50

        # Check that the second device is the second known device
        reading2 = queue.get_nowait()
        assert reading2.device.address == "AA:BB:CC:DD:EE:FF"
        assert reading2.rssi == -70

        # Check that the queue is empty (unknown device was filtered out)
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_scanner_requires_known_addresses(self):
        """Test that the scanner requires known_addresses parameter."""
        # Verify that creating a scanner without known_addresses raises an error
        with pytest.raises(TypeError):
            BluetoothScanner()  # type: ignore
