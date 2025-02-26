"""Tests for Sensor class."""

from datetime import datetime

import pytest

from bluetooth_route_timer.route import Sensor


@pytest.fixture
def sensor():
    """Create a test sensor."""
    return Sensor(name="test_sensor", address="00:11:22:33:44:55")


def test_sensor_creation(sensor):
    """Test sensor initialization."""
    assert sensor.name == "test_sensor"
    assert sensor.address == "00:11:22:33:44:55"
    assert sensor.rssi_history == {}


def test_add_rssi(sensor):
    """Test adding RSSI values."""
    now = datetime.now()
    sensor.add_rssi(-50, now)
    assert sensor.rssi_history[now] == -50


def test_add_rssi_without_timestamp(sensor):
    """Test adding RSSI values without timestamp."""
    sensor.add_rssi(-50)
    assert len(sensor.rssi_history) == 1
    assert list(sensor.rssi_history.values())[0] == -50
