"""Route scanner module for Bluetooth positioning system."""

import asyncio
import logging

from bluetooth_route_timer.route import Route
from bluetooth_route_timer.scanner import BluetoothScanner

# Configure logging
logger = logging.getLogger(__name__)

# Timer constants
ABSOLUTE_END_TIMER_DURATION_SEC = 30
SCAN_END_TIMER_DURATION_SEC = 15


async def scan_loop(scanner: BluetoothScanner, route: Route) -> Route:
    """Main scanning loop."""
    last_end_signal = None
    end_timer = None
    absolute_end_timer = None

    mac_to_sensor_lookup = route.get_mac_to_sensor_lookup()

    try:
        async for reading in scanner.scan_devices():
            # Check if either timer has completed
            if (end_timer and end_timer.done()) or (absolute_end_timer and absolute_end_timer.done()):
                timer_type = "completion" if end_timer and end_timer.done() else "absolute"
                logger.info(f"{timer_type.capitalize()} timer expired, ending scan...")
                break

            # Get sensor if this is a known device
            sensor = mac_to_sensor_lookup.get(reading.device.address)
            if sensor:
                logger.info(f"Sensor {sensor.name} RSSI: {reading.rssi} dBm")
                sensor.add_rssi(reading.rssi, reading.timestamp)

                is_end_sensor = route.is_end_sensor(sensor)
                if is_end_sensor:
                    end_signal = route.end.get_strongest_signal()

                    # Start timers if we detected possible final end signal
                    if end_signal:
                        # Start absolute end timer on first end signal
                        if absolute_end_timer is None:
                            absolute_end_timer = asyncio.create_task(asyncio.sleep(ABSOLUTE_END_TIMER_DURATION_SEC))
                            logger.info(f"Starting {ABSOLUTE_END_TIMER_DURATION_SEC} second absolute timer...")

                        if last_end_signal is None or end_signal.strength > last_end_signal.strength:
                            last_end_signal = end_signal

                            # Reset the 5-second timer on new strongest signal
                            if end_timer is not None:
                                end_timer.cancel()
                            end_timer = asyncio.create_task(asyncio.sleep(SCAN_END_TIMER_DURATION_SEC))
                            logger.info(f"Starting {SCAN_END_TIMER_DURATION_SEC} second completion timer...")

            else:
                logger.debug(f"Found unknown device: {reading.device.address}")

        return route
    except asyncio.CancelledError:
        logger.info("Scan stopped")
        raise
    finally:
        if end_timer:
            end_timer.cancel()
        if absolute_end_timer:
            absolute_end_timer.cancel()
        await scanner.stop_scan()
