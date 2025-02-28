"""Position calculator module for processing RSSI data and calculating positions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class PointType(Enum):
    """Type of point on the route."""

    START = auto()
    CHECKPOINT = auto()
    END = auto()


@dataclass
class Sensor:
    """Represents a Bluetooth sensor.

    Args:
        name: Semantic name of the sensor (e.g. "a_line_start_1")
        address: MAC address of the sensor
    """

    name: str
    address: str
    rssi_history: dict[datetime, float] = field(default_factory=dict)

    def add_rssi(self, rssi: float, timestamp: datetime | None = None) -> None:
        """Add RSSI reading with timestamp."""
        self.rssi_history[timestamp or datetime.now()] = rssi

    def has_readings(self) -> bool:
        """Check if there are any RSSI readings."""
        return bool(self.rssi_history)


@dataclass
class SignalReading:
    """Represents a signal reading with timestamp and strength.

    Args:
        timestamp: When the signal was recorded
        strength: Signal strength in dBm
    """

    timestamp: datetime
    strength: float


@dataclass
class RoutePoint(ABC):
    """Abstract base class for a point on the route."""

    type: PointType
    name: str

    @abstractmethod
    def get_strongest_signal(self) -> SignalReading | None:
        """Get timestamp when the point had strongest signal.

        Returns:
            SignalReading with timestamp and signal strength if sensors have readings,
            None otherwise.
        """
        pass

    def has_sensor(self, sensor: Sensor) -> bool:
        """Check if the point has a specific sensor."""
        return False


@dataclass
class RoutePointSingleSensor(RoutePoint):
    """A point on the route with a single sensor."""

    sensor: Sensor

    def get_strongest_signal(self) -> SignalReading | None:
        """Get timestamp when the sensor had strongest signal.

        Returns:
            SignalReading with timestamp and signal strength if sensor has readings,
            None otherwise.
        """
        if not self.sensor.has_readings():
            return None

        # Find timestamp with strongest signal
        strongest_time = max(self.sensor.rssi_history.keys(), key=lambda t: self.sensor.rssi_history[t])
        return SignalReading(timestamp=strongest_time, strength=self.sensor.rssi_history[strongest_time])

    def has_sensor(self, sensor: Sensor) -> bool:
        """Check if the point has a specific sensor."""
        return self.sensor == sensor


@dataclass
class RoutePointDualSensor(RoutePoint):
    """A point on the route with two sensors."""

    sensor1: Sensor
    sensor2: Sensor

    def get_strongest_signal(self) -> SignalReading | None:
        """Get timestamp when both sensors had strongest combined signal.

        Returns:
            SignalReading with timestamp and combined signal strength if both sensors have readings
            at the same time, None otherwise.

        When multiple timestamps have equal combined signal strength, selects the one
        where the individual signals are most balanced (closest to each other).
        """
        # Get timestamps where we have readings from both sensors
        common_times = set(self.sensor1.rssi_history.keys()) & set(self.sensor2.rssi_history.keys())
        if not common_times:
            return None

        # First find the strongest combined signal value
        strongest_combined = max(
            common_times,
            key=lambda t: self.sensor1.rssi_history[t] + self.sensor2.rssi_history[t],
        )
        max_combined_strength = (
            self.sensor1.rssi_history[strongest_combined] + self.sensor2.rssi_history[strongest_combined]
        )

        # Find all timestamps that have this combined strength
        strongest_times = [
            t
            for t in common_times
            if (self.sensor1.rssi_history[t] + self.sensor2.rssi_history[t]) == max_combined_strength
        ]

        if len(strongest_times) == 1:
            # If only one timestamp has max strength, return it
            strongest_time = strongest_times[0]
        else:
            # If multiple timestamps have max strength, select the one with most balanced signals
            strongest_time = min(
                strongest_times, key=lambda t: abs(self.sensor1.rssi_history[t] - self.sensor2.rssi_history[t])
            )

        combined_signal = self.sensor1.rssi_history[strongest_time] + self.sensor2.rssi_history[strongest_time]
        return SignalReading(timestamp=strongest_time, strength=combined_signal)

    def has_sensor(self, sensor: Sensor) -> bool:
        """Check if the point has a specific sensor."""
        return sensor in (self.sensor1, self.sensor2)


@dataclass
class RoutePassage:
    """Represents a passage through a route point.

    Args:
        point: The route point that was passed
        timestamp: When the point was passed
        signal_strength: Signal strength at the point
    """

    point: RoutePoint
    timestamp: datetime
    signal_strength: float


@dataclass
class RouteTime:
    """Represents the timing information for a route.

    Args:
        start_time: When the route was started
        end_time: When the route was completed
        duration_seconds: Total duration in seconds
    """

    start_time: datetime
    end_time: datetime
    duration_seconds: float


@dataclass
class Route:
    """A route with start, end, and optional checkpoint points."""

    name: str
    start: RoutePoint
    end: RoutePoint
    checkpoints: list[RoutePoint] = field(default_factory=list)

    def get_all_points(self) -> list[RoutePoint]:
        """Get all points in order: start -> checkpoints -> end."""
        return [self.start] + self.checkpoints + [self.end]

    def get_point_passages(self) -> list[RoutePassage]:
        """Get list of points passed in chronological order with signal strengths."""
        passages = []
        for point in self.get_all_points():
            signal = point.get_strongest_signal()
            if signal:
                passages.append(RoutePassage(point=point, timestamp=signal.timestamp, signal_strength=signal.strength))

        # Sort by timestamp
        return sorted(passages, key=lambda x: x.timestamp)

    def is_end_sensor(self, sensor: Sensor) -> bool:
        return self.end.has_sensor(sensor)

    def get_total_time(self) -> RouteTime | None:
        """Calculate total time from start to end point.

        Returns:
            RouteTime with start_time, end_time, and duration if both points
            have signals, None otherwise.
        """
        start_signal = self.start.get_strongest_signal()
        end_signal = self.end.get_strongest_signal()

        if not start_signal or not end_signal:
            return None

        duration = (end_signal.timestamp - start_signal.timestamp).total_seconds()

        return RouteTime(start_time=start_signal.timestamp, end_time=end_signal.timestamp, duration_seconds=duration)

    def get_mac_to_sensor_lookup(self) -> dict:
        """Create mapping of MAC addresses to sensors for the route.

        Returns:
            Dictionary mapping sensor MAC addresses to Sensor objects.
        """
        lookup = {}
        for point in self.get_all_points():
            if isinstance(point, RoutePointDualSensor):
                lookup[point.sensor1.address] = point.sensor1
                lookup[point.sensor2.address] = point.sensor2
            elif isinstance(point, RoutePointSingleSensor):
                lookup[point.sensor.address] = point.sensor
        return lookup

    def get_known_addresses(self) -> set[str]:
        """Get the set of known MAC addresses for all sensors in the route.

        Returns:
            Set of MAC addresses for all sensors in the route.
        """
        return set(self.get_mac_to_sensor_lookup().keys())
