import pytest
from unittest.mock import patch, MagicMock
from app.services.weather_service import (
    WeatherDataService,
    InvalidCoordinatesError,
    WeatherAPIError,
    WeatherError,
    WMO_CODE_MAP,
)


def test_invalid_coordinates_raise_error():
    service = WeatherDataService()

    # Latitude out of bounds (> 90)
    with pytest.raises(InvalidCoordinatesError) as exc:
        service.fetch_weather(latitude=95.0, longitude=76.21)
    assert "Latitude 95.0 is out of valid range" in str(exc.value)

    # Longitude out of bounds (< -180)
    with pytest.raises(InvalidCoordinatesError) as exc:
        service.fetch_weather(latitude=10.52, longitude=-185.0)
    assert "Longitude -185.0 is out of valid range" in str(exc.value)


def test_invalid_date_format_raises_error():
    service = WeatherDataService()
    with pytest.raises(WeatherError) as exc:
        service.fetch_weather(
            latitude=10.5276,
            longitude=76.2144,
            start_date="27-08-2026", # invalid format, expected YYYY-MM-DD
            end_date="2026-08-29",
        )
    assert "Invalid date format" in str(exc.value)


def test_successful_weather_normalization():
    mock_payload = {
        "latitude": 10.52,
        "longitude": 76.21,
        "elevation": 25.0,
        "timezone": "Asia/Kolkata",
        "daily": {
            "time": ["2026-08-27", "2026-08-28"],
            "temperature_2m_max": [30.2, 29.5],
            "temperature_2m_min": [24.1, 23.8],
            "temperature_2m_mean": [26.4, 25.9],
            "relative_humidity_2m_mean": [88, 91],
            "precipitation_sum": [1.5, 6.2],
            "rain_sum": [1.0, 4.5],
            "weather_code": [51, 80],
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    service = WeatherDataService()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = service.fetch_weather(latitude=10.5276, longitude=76.2144, forecast_days=2)

        assert result["status"] == "success"
        assert result["source"] == "Open-Meteo"
        assert result["total_days"] == 2
        assert result["location"]["latitude"] == 10.52
        assert result["location"]["longitude"] == 76.21
        assert result["location"]["elevation"] == 25.0

        records = result["daily_forecasts"]
        assert len(records) == 2

        # Day 1 Verification
        day1 = records[0]
        assert day1["date"] == "2026-08-27"
        assert day1["temp_max_celsius"] == 30.2
        assert day1["temp_min_celsius"] == 24.1
        assert day1["temp_mean_celsius"] == 26.4
        assert day1["humidity_mean_pct"] == 88.0
        assert day1["precipitation_mm"] == 1.5
        assert day1["rain_mm"] == 1.0
        assert day1["weather_code"] == 51
        assert day1["weather_condition"] == "Light drizzle"

        # Day 2 Verification
        day2 = records[1]
        assert day2["weather_code"] == 80
        assert day2["weather_condition"] == "Slight rain showers"

        # Verify request parameters
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["latitude"] == 10.5276
        assert kwargs["params"]["longitude"] == 76.2144
        assert kwargs["params"]["forecast_days"] == 2


def test_http_error_handling():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    service = WeatherDataService()

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(WeatherAPIError) as exc:
            service.fetch_weather(latitude=10.5276, longitude=76.2144)
        assert "HTTP 500" in str(exc.value)


def test_wmo_code_mapping():
    assert WMO_CODE_MAP[0] == "Clear sky"
    assert WMO_CODE_MAP[61] == "Slight rain"
    assert WMO_CODE_MAP[95] == "Thunderstorm"
