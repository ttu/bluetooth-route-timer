"""Example usage of the Bluetooth positioning system."""

import asyncio
import logging

from route import PointType, Route, RoutePointDualSensor, RoutePointSingleSensor, Sensor
from route_timer import scan_loop
from scanner import BluetoothScanner

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define route with sensors
ROUTE = Route(
    name="route_a",
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

ROUTE_SINGLE_SENSOR = Route(
    name="route_b",
    start=RoutePointSingleSensor(
        type=PointType.START,
        name="start",
        sensor=Sensor(name="start_1", address="C5:7D:89:63:9E:B9"),
    ),
    end=RoutePointSingleSensor(
        type=PointType.END,
        name="end",
        sensor=Sensor(name="end_1", address="D2:A3:6E:C8:E0:25"),
    ),
    checkpoints=[],
)


async def main():
    """Main function to demonstrate Bluetooth positioning."""
    try:
        scanner = BluetoothScanner()
        logger.info("Starting Bluetooth scan... Press Ctrl+C to stop")
        finished_route = await scan_loop(scanner, ROUTE_SINGLE_SENSOR)

        total_time = finished_route.get_total_time()
        logger.info(
            f"New best time: {total_time.duration_seconds:.1f} seconds "
            f"(from {total_time.start_time.strftime('%H:%M:%S')} "
            f"to {total_time.end_time.strftime('%H:%M:%S')})"
        )

        passages = finished_route.get_point_passages()
        logger.info(f"Detected {len(passages)} passages:")
        for passage in passages:
            logger.info(
                f"- {passage.point.name} at {passage.timestamp.strftime('%H:%M:%S.%f')[:-3]} "
                f"(signal: {passage.signal_strength:.1f} dBm)"
            )
    except KeyboardInterrupt:
        # Handle Ctrl+C/Cmd+C gracefully
        print("Stopping scanner...")
        await scanner.stop_scan()
    finally:
        # Ensure cleanup happens
        await scanner.stop_scan()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Application stopped by user")
