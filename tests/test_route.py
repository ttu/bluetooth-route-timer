"""Tests for Route and RoutePoint classes."""

from datetime import datetime, timedelta

import pytest

from bluetooth_route_timer.route import (
    PointType,
    Route,
    RoutePassage,
    RoutePointDualSensor,
    RoutePointSingleSensor,
    RouteTime,
    Sensor,
    SignalReading,
)


@pytest.fixture
def sensors():
    """Create test sensors."""
    return {
        "start1": Sensor(name="start1", address="00:11:22:33:44:55"),
        "start2": Sensor(name="start2", address="AA:BB:CC:DD:EE:FF"),
        "end1": Sensor(name="end1", address="11:22:33:44:55:66"),
        "end2": Sensor(name="end2", address="BB:CC:DD:EE:FF:00"),
        "single": Sensor(name="single", address="CC:DD:EE:FF:00:11"),
    }


@pytest.fixture
def route(sensors):
    """Create a test route."""
    return Route(
        name="test_route",
        start=RoutePointDualSensor(
            type=PointType.START,
            name="start",
            sensor1=sensors["start1"],
            sensor2=sensors["start2"],
        ),
        end=RoutePointDualSensor(
            type=PointType.END,
            name="end",
            sensor1=sensors["end1"],
            sensor2=sensors["end2"],
        ),
        checkpoints=[
            RoutePointSingleSensor(
                type=PointType.CHECKPOINT,
                name="checkpoint",
                sensor=sensors["single"],
            )
        ],
    )


def test_route_creation(route):
    """Test route initialization."""
    assert route.name == "test_route"
    assert route.start.type == PointType.START
    assert route.end.type == PointType.END
    assert len(route.checkpoints) == 1
    assert route.checkpoints[0].type == PointType.CHECKPOINT
    assert route.checkpoints[0].name == "checkpoint"
    assert isinstance(route.checkpoints[0], RoutePointSingleSensor)


def test_route_point_single_sensor_strongest_signal(sensors):
    """Test getting strongest signal from a single sensor point."""
    point = RoutePointSingleSensor(type=PointType.CHECKPOINT, name="test", sensor=sensors["single"])

    # No readings yet
    assert point.get_strongest_signal() is None

    # Add some readings
    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    sensors["single"].add_rssi(-70, reference_time)
    sensors["single"].add_rssi(-50, reference_time + timedelta(seconds=1))  # Strongest
    sensors["single"].add_rssi(-60, reference_time + timedelta(seconds=2))

    signal = point.get_strongest_signal()
    assert isinstance(signal, SignalReading)
    assert signal.timestamp == reference_time + timedelta(seconds=1)
    assert signal.strength == -50


def test_route_point_dual_sensor_strongest_signal(sensors):
    """Test getting strongest signal from a dual sensor point."""
    point = RoutePointDualSensor(
        type=PointType.START,
        name="start",
        sensor1=sensors["start1"],
        sensor2=sensors["start2"],
    )

    # No readings yet
    assert point.get_strongest_signal() is None

    # Add some readings to only one sensor
    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    sensors["start1"].add_rssi(-50, reference_time)
    assert point.get_strongest_signal() is None  # Still None because both sensors need readings

    # Add readings to both sensors at different times
    sensors["start2"].add_rssi(-60, reference_time + timedelta(seconds=1))
    assert point.get_strongest_signal() is None  # Still None because no common timestamps

    # Add readings at the same time
    common_time = reference_time + timedelta(seconds=2)
    sensors["start1"].add_rssi(-55, common_time)
    sensors["start2"].add_rssi(-65, common_time)

    signal = point.get_strongest_signal()
    assert isinstance(signal, SignalReading)
    assert signal.timestamp == common_time
    assert signal.strength == -55 + -65  # Combined strength


def test_route_point_dual_sensor_signal_balance(sensors):
    """Test that when combined signals are equal, the most balanced signals are selected."""
    point = RoutePointDualSensor(
        type=PointType.START,
        name="test_point",
        sensor1=sensors["start1"],
        sensor2=sensors["start2"],
    )

    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    # Add signals at different times with same combined strength (-110)
    # t=0: -50 and -60 (difference: 10)
    # t=1: -70 and -40 (difference: 30)
    sensors["start1"].add_rssi(-50, reference_time)  # More balanced
    sensors["start2"].add_rssi(-60, reference_time)  # More balanced
    sensors["start1"].add_rssi(-70, reference_time + timedelta(seconds=1))  # Less balanced
    sensors["start2"].add_rssi(-40, reference_time + timedelta(seconds=1))  # Less balanced

    signal = point.get_strongest_signal()
    assert isinstance(signal, SignalReading)
    # Should select t=0 because -50 and -60 are more balanced than -70 and -40
    assert signal.timestamp == reference_time
    assert signal.strength == -110
    # Verify the signals at the selected time are more balanced
    signal1 = sensors["start1"].rssi_history[signal.timestamp]
    signal2 = sensors["start2"].rssi_history[signal.timestamp]
    assert abs(signal1 - signal2) == 10  # Difference between -50 and -60


def test_route_with_mixed_points(sensors):
    """Test route with both single and dual sensor points."""
    route = Route(
        name="mixed_route",
        start=RoutePointDualSensor(
            type=PointType.START,
            name="start",
            sensor1=sensors["start1"],
            sensor2=sensors["start2"],
        ),
        end=RoutePointSingleSensor(
            type=PointType.END,
            name="end",
            sensor=sensors["single"],
        ),
        checkpoints=[],
    )

    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    start_time = reference_time + timedelta(seconds=1)

    # Add start signals (dual sensor)
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)
    sensors["start1"].add_rssi(-40, start_time)
    sensors["start2"].add_rssi(-50, start_time)

    # Add end signal (single sensor) 10 seconds later
    sensors["single"].add_rssi(-55, reference_time + timedelta(seconds=10))
    end_time = reference_time + timedelta(seconds=11)
    sensors["single"].add_rssi(-40, end_time)  # Strongest signal + 11
    sensors["single"].add_rssi(-50, reference_time + timedelta(seconds=12))  # Weaker signal + 12

    route_time = route.get_total_time()
    assert isinstance(route_time, RouteTime)
    assert route_time.start_time == start_time
    assert route_time.end_time == end_time
    assert route_time.duration_seconds == (end_time - start_time).total_seconds()


def test_route_point_passages(route, sensors):
    """Test getting point passages in chronological order."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add signals in non-chronological order
    # End point first (but with later timestamp)
    end_time = reference_time + timedelta(seconds=10)
    sensors["end1"].add_rssi(-55, end_time)
    sensors["end2"].add_rssi(-65, end_time)

    # Start point (earlier timestamp)
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)

    # Checkpoint (middle timestamp)
    cp_time = reference_time + timedelta(seconds=5)
    sensors["single"].add_rssi(-45, cp_time)

    passages = route.get_point_passages()
    assert len(passages) == 3
    assert isinstance(passages[0], RoutePassage)
    assert isinstance(passages[1], RoutePassage)
    assert isinstance(passages[2], RoutePassage)

    # Check chronological order
    assert passages[0].timestamp == reference_time
    assert passages[1].timestamp == cp_time
    assert passages[2].timestamp == end_time

    # Check points
    assert passages[0].point == route.start
    assert passages[1].point == route.checkpoints[0]
    assert passages[2].point == route.end


def test_route_total_time_with_checkpoints(route, sensors):
    """Test calculating total route time with checkpoints."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add start signals
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)

    # Add checkpoint signal
    cp_time = reference_time + timedelta(seconds=5)
    sensors["single"].add_rssi(-45, cp_time)

    # Add end signals 10 seconds later
    end_time = reference_time + timedelta(seconds=11)
    sensors["end1"].add_rssi(-40, end_time)  # Strongest signal
    sensors["end2"].add_rssi(-50, end_time)

    route_time = route.get_total_time()
    assert isinstance(route_time, RouteTime)
    assert route_time.start_time == reference_time
    assert route_time.end_time == end_time
    assert route_time.duration_seconds == (end_time - reference_time).total_seconds()


def test_route_total_time(route, sensors):
    """Test calculating total route time."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add start signals
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)

    # Add end signals 10 seconds later
    end_time = reference_time + timedelta(seconds=10)
    sensors["end1"].add_rssi(-55, end_time)
    sensors["end2"].add_rssi(-65, end_time)

    route_time = route.get_total_time()
    assert isinstance(route_time, RouteTime)
    assert route_time.start_time == reference_time
    assert route_time.end_time == end_time
    assert route_time.duration_seconds == 10.0


def test_get_total_time_no_signals(route):
    """Test total time calculation with no signals."""
    assert route.get_total_time() is None


def test_get_total_time_missing_end(route, sensors):
    """Test total time calculation with missing end signal."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)
    assert route.get_total_time() is None


def test_get_total_time_missing_start(route, sensors):
    """Test total time calculation with missing start signal."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)
    sensors["end1"].add_rssi(-50, reference_time)
    sensors["end2"].add_rssi(-60, reference_time)
    assert route.get_total_time() is None


def test_get_total_time_success(route, sensors):
    """Test successful total time calculation."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add start signals
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)

    # Add end signals 10 seconds later
    end_time = reference_time + timedelta(seconds=10)
    sensors["end1"].add_rssi(-55, end_time)
    sensors["end2"].add_rssi(-65, end_time)

    result = route.get_total_time()
    assert isinstance(result, RouteTime)
    assert result.start_time == reference_time
    assert result.end_time == end_time
    assert result.duration_seconds == 10.0


def test_is_end_sensor(route, sensors):
    """Test is_end_sensor method."""
    # Test with end sensors
    assert route.is_end_sensor(sensors["end1"]) is True
    assert route.is_end_sensor(sensors["end2"]) is True

    # Test with non-end sensors
    assert route.is_end_sensor(sensors["start1"]) is False
    assert route.is_end_sensor(sensors["start2"]) is False
    assert route.is_end_sensor(sensors["single"]) is False

    # Test with None
    assert route.is_end_sensor(None) is False


def test_get_total_time_multiple_signals(route, sensors):
    """Test total time calculation with multiple signals."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add multiple start signals with different strengths
    sensors["start1"].add_rssi(-70, reference_time - timedelta(seconds=5))
    sensors["start2"].add_rssi(-80, reference_time - timedelta(seconds=5))

    sensors["start1"].add_rssi(-50, reference_time)  # Strongest combined
    sensors["start2"].add_rssi(-60, reference_time)

    sensors["start1"].add_rssi(-55, reference_time + timedelta(seconds=2))
    sensors["start2"].add_rssi(-65, reference_time + timedelta(seconds=2))

    # Add multiple end signals with different strengths
    sensors["end1"].add_rssi(-75, reference_time + timedelta(seconds=8))
    sensors["end2"].add_rssi(-85, reference_time + timedelta(seconds=8))

    end_time = reference_time + timedelta(seconds=10)
    sensors["end1"].add_rssi(-55, end_time)  # Strongest combined
    sensors["end2"].add_rssi(-65, end_time)

    sensors["end1"].add_rssi(-60, reference_time + timedelta(seconds=12))
    sensors["end2"].add_rssi(-70, reference_time + timedelta(seconds=12))

    result = route.get_total_time()
    assert isinstance(result, RouteTime)
    assert result.start_time == reference_time
    assert result.end_time == end_time
    assert result.duration_seconds == 10.0
