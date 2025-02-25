"""Tests for Route and RoutePoint classes."""

from datetime import datetime, timedelta

import pytest
from route import PointType, Route, RoutePointDualSensor, RoutePointSingleSensor, Sensor


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
        checkpoints=[],
    )


def test_route_creation(route):
    """Test route initialization."""
    assert route.name == "test_route"
    assert route.start.type == PointType.START
    assert route.end.type == PointType.END
    assert route.checkpoints == []


def test_route_point_single_sensor(sensors):
    """Test getting strongest signal from a single sensor point."""
    point = RoutePointSingleSensor(
        type=PointType.CHECKPOINT,
        name="test_point",
        sensor=sensors["single"],
    )

    reference_time = datetime(2024, 1, 1, 12, 0, 0)  # Fixed reference time
    # Add signals at different times
    sensors["single"].add_rssi(-80, reference_time - timedelta(seconds=1))
    sensors["single"].add_rssi(-70, reference_time)
    sensors["single"].add_rssi(-50, reference_time + timedelta(seconds=1))

    time, strength = point.get_strongest_signal()
    # The strongest signal should be at reference_time + 1 second
    assert time == reference_time + timedelta(seconds=1)
    assert strength == -50


def test_route_point_dual_sensor_strongest_signal(sensors):
    """Test getting strongest combined signal from a dual sensor point."""
    point = RoutePointDualSensor(
        type=PointType.START,
        name="test_point",
        sensor1=sensors["start1"],
        sensor2=sensors["start2"],
    )

    reference_time = datetime(2024, 1, 1, 12, 0, 0)  # Fixed reference time
    # Add signals at different times
    sensors["start1"].add_rssi(-80, reference_time - timedelta(seconds=1))
    sensors["start1"].add_rssi(-70, reference_time)
    sensors["start1"].add_rssi(-50, reference_time + timedelta(seconds=1))

    sensors["start2"].add_rssi(-80, reference_time - timedelta(seconds=1))
    sensors["start2"].add_rssi(-60, reference_time)
    sensors["start2"].add_rssi(-40, reference_time + timedelta(seconds=1))

    time, strength = point.get_strongest_signal()
    # The strongest combined signal should be at reference_time + 1 second
    assert time == reference_time + timedelta(seconds=1)
    assert strength == -90


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

    time, strength = point.get_strongest_signal()
    # Should select t=0 because -50 and -60 are more balanced than -70 and -40
    assert time == reference_time
    assert strength == -110
    # Verify the signals at the selected time are more balanced
    signal1 = sensors["start1"].rssi_history[time]
    signal2 = sensors["start2"].rssi_history[time]
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

    start_time, finish_time, duration = route.get_total_time()
    assert start_time == start_time
    assert finish_time == end_time
    assert duration == (end_time - start_time).total_seconds()


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

    start_time, finish_time, duration = route.get_total_time()
    assert start_time == reference_time
    assert finish_time == end_time
    assert duration == 10.0


def test_route_point_passages(route, sensors):
    """Test getting route passages in chronological order."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add signals in reverse order
    end_time = reference_time + timedelta(seconds=10)
    sensors["end1"].add_rssi(-55, end_time)
    sensors["end2"].add_rssi(-65, end_time)

    start_time = reference_time
    sensors["start1"].add_rssi(-50, start_time)
    sensors["start2"].add_rssi(-60, start_time)

    passages = route.get_point_passages()
    assert len(passages) == 2

    # Check chronological order
    first_point, first_time, _ = passages[0]
    second_point, second_time, _ = passages[1]

    assert first_point.type == PointType.START
    assert second_point.type == PointType.END
    assert first_time == start_time
    assert second_time == end_time


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
    end_time = reference_time + timedelta(seconds=30)

    # Add start signals
    sensors["start1"].add_rssi(-50, reference_time)
    sensors["start2"].add_rssi(-60, reference_time)

    # Add end signals
    sensors["end1"].add_rssi(-55, end_time)
    sensors["end2"].add_rssi(-65, end_time)

    result = route.get_total_time()
    assert result is not None

    actual_start, actual_end, duration = result
    assert actual_start == reference_time
    assert actual_end == end_time
    assert duration == 30.0


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
    """Test total time calculation with multiple signals at each point."""
    reference_time = datetime(2024, 1, 1, 12, 0, 0)

    # Add multiple start signals
    sensors["start1"].add_rssi(-60, reference_time)
    sensors["start2"].add_rssi(-70, reference_time)
    sensors["start1"].add_rssi(-50, reference_time + timedelta(seconds=1))  # Stronger signal
    sensors["start2"].add_rssi(-55, reference_time + timedelta(seconds=1))  # Stronger signal

    # Add multiple end signals
    end_time = reference_time + timedelta(seconds=20)
    sensors["end1"].add_rssi(-65, end_time - timedelta(seconds=1))
    sensors["end2"].add_rssi(-75, end_time - timedelta(seconds=1))
    sensors["end1"].add_rssi(-45, end_time)  # Stronger signal
    sensors["end2"].add_rssi(-50, end_time)  # Stronger signal

    result = route.get_total_time()
    assert result is not None

    start, end, duration = result
    # Should use the timestamps of strongest combined signals
    assert start == reference_time + timedelta(seconds=1)
    assert end == end_time
    assert duration == 19.0  # 20 - 1 seconds between strongest signals
