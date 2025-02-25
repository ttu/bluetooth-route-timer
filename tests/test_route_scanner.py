"""Tests for route scanner functionality."""

import asyncio
from datetime import datetime, timedelta
from typing import AsyncGenerator

import pytest
from bleak.backends.device import BLEDevice
from route import PointType, Route, RoutePointDualSensor, Sensor
from route_timer import scan_loop
from scanner import BluetoothScanner, DeviceReading

# Test route definition
TEST_ROUTE = Route(
    name="test_route",
    start=RoutePointDualSensor(
        type=PointType.START,
        name="start",
        sensor1=Sensor(name="start_1", address="00:11:22:33:44:55"),
        sensor2=Sensor(name="start_2", address="AA:BB:CC:DD:EE:FF"),
    ),
    end=RoutePointDualSensor(
        type=PointType.END,
        name="end",
        sensor1=Sensor(name="end_1", address="11:22:33:44:55:66"),
        sensor2=Sensor(name="end_2", address="BB:CC:DD:EE:FF:00"),
    ),
    checkpoints=[
        RoutePointDualSensor(
            type=PointType.CHECKPOINT,
            name="checkpoint_1",
            sensor1=Sensor(name="cp1_1", address="22:33:44:55:66:77"),
            sensor2=Sensor(name="cp1_2", address="CC:DD:EE:FF:00:11"),
        )
    ],
)


class MockBLEDevice(BLEDevice):
    """Mock BLE device that doesn't require all constructor arguments."""

    def __init__(self, address: str, name: str):
        super().__init__(
            address=address,
            name=name,
            details={},  # Empty details for testing
            rssi=0,  # Default RSSI, will be overridden in DeviceReading
        )


class MockScanner(BluetoothScanner):
    """Mock scanner that yields predefined readings."""

    def __init__(self, readings: list[DeviceReading]):
        super().__init__()
        self.readings = readings
        self.stopped = False
        self._scan_task: asyncio.Task | None = None

    async def scan_devices(self) -> AsyncGenerator[DeviceReading, None]:
        """Yield predefined readings until stopped."""
        try:
            for reading in self.readings:
                if self.stopped:
                    break
                yield reading
                # Small delay to simulate real scanning
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            self.stopped = True
            raise
        finally:
            self.stopped = True

    async def stop_scan(self) -> None:
        """Mark scanner as stopped."""
        self.stopped = True
        await super().stop_scan()


@pytest.fixture
def mock_readings():
    """Create test device readings."""
    base_time = datetime.now()
    readings = []

    # Create mock BLE devices for our sensors
    devices = {
        TEST_ROUTE.start.sensor1.address: MockBLEDevice(TEST_ROUTE.start.sensor1.address, "Start 1"),
        TEST_ROUTE.start.sensor2.address: MockBLEDevice(TEST_ROUTE.start.sensor2.address, "Start 2"),
        TEST_ROUTE.end.sensor1.address: MockBLEDevice(TEST_ROUTE.end.sensor1.address, "End 1"),
        TEST_ROUTE.end.sensor2.address: MockBLEDevice(TEST_ROUTE.end.sensor2.address, "End 2"),
        "unknown": MockBLEDevice("unknown", "Unknown Device"),
    }

    # Add start point readings (stronger signal)
    readings.extend(
        [
            DeviceReading(devices[TEST_ROUTE.start.sensor1.address], base_time, -50),
            DeviceReading(devices[TEST_ROUTE.start.sensor2.address], base_time, -55),
        ]
    )

    # Add some unknown device readings
    readings.append(DeviceReading(devices["unknown"], base_time + timedelta(seconds=1), -70))

    # Add end point readings (weaker first)
    end_time = base_time + timedelta(seconds=10)
    readings.extend(
        [
            DeviceReading(devices[TEST_ROUTE.end.sensor1.address], end_time, -70),
            DeviceReading(devices[TEST_ROUTE.end.sensor2.address], end_time, -75),
        ]
    )

    # Add end point readings (stronger signal)
    better_end_time = base_time + timedelta(seconds=11)
    readings.extend(
        [
            DeviceReading(devices[TEST_ROUTE.end.sensor1.address], better_end_time, -45),
            DeviceReading(devices[TEST_ROUTE.end.sensor2.address], better_end_time, -50),
        ]
    )

    return readings


@pytest.mark.asyncio
async def test_scan_loop_basic_functionality(mock_readings, caplog):
    """Test basic scanning functionality."""
    caplog.set_level("DEBUG")  # Lower log level to see more details
    scanner = MockScanner(mock_readings)

    # Run scan loop
    finished_route = await scan_loop(scanner, TEST_ROUTE)

    # Check that we got RSSI readings
    rssi_logs = [record.message for record in caplog.records if "RSSI" in record.message]
    assert len(rssi_logs) == 6

    # Check that passages were detected
    passages = finished_route.get_point_passages()
    assert len(passages) == 2

    # Verify the final time calculation
    total_time = finished_route.get_total_time()
    assert total_time[2] == 11.0


@pytest.mark.asyncio
async def test_scan_loop_cancellation(mock_readings):
    """Test that scan loop can be cancelled."""
    scanner = MockScanner(mock_readings)

    # Create a task for the scan loop
    scan_task = asyncio.create_task(scan_loop(scanner, TEST_ROUTE))

    # Let it run for a bit
    await asyncio.sleep(0.1)

    # Cancel the task and wait for it to finish
    scan_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass

    # Give the scanner a moment to process the cancellation
    await asyncio.sleep(0.1)

    # Verify that the scanner was stopped
    assert scanner.stopped

    # Verify that no more readings are yielded
    async for _ in scanner.scan_devices():
        pytest.fail("Scanner should not yield any more readings after being stopped")


@pytest.mark.asyncio
async def test_scan_loop_unknown_devices(mock_readings, caplog):
    """Test handling of unknown devices."""
    caplog.set_level("DEBUG")
    scanner = MockScanner(mock_readings)

    # Run scan loop
    await scan_loop(scanner, TEST_ROUTE)

    # Check that unknown devices were logged
    unknown_logs = [record.message for record in caplog.records if "unknown" in record.message.lower()]
    assert len(unknown_logs) == 1
