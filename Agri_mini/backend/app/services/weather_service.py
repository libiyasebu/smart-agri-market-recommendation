import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.config import settings


class WeatherError(Exception):
    """Base exception for weather data acquisition errors."""
    pass


class InvalidCoordinatesError(WeatherError):
    """Raised when latitude or longitude coordinates are out of valid bounds."""
    pass


class WeatherAPIError(WeatherError):
    """Raised when the Open-Meteo API request fails or returns an error response."""
    pass


# WMO Weather interpretation codes (WW) mapping
WMO_CODE_MAP: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class WeatherDataService:
    """Service to fetch and normalize agro-meteorological data from Open-Meteo."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: int = 15,
        default_timezone: str = "Asia/Kolkata",
    ):
        self.base_url = base_url or settings.OPEN_METEO_BASE_URL
        self.timeout = timeout
        self.default_timezone = default_timezone

    def _validate_coordinates(self, latitude: float, longitude: float) -> None:
        """Validates geographic latitude and longitude bounds."""
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise InvalidCoordinatesError(
                f"Coordinates must be numeric values. Received latitude={latitude!r}, longitude={longitude!r}"
            )
        if not (-90.0 <= float(latitude) <= 90.0):
            raise InvalidCoordinatesError(
                f"Latitude {latitude} is out of valid range [-90.0, 90.0]."
            )
        if not (-180.0 <= float(longitude) <= 180.0):
            raise InvalidCoordinatesError(
                f"Longitude {longitude} is out of valid range [-180.0, 180.0]."
            )

    def fetch_weather(
        self,
        latitude: float,
        longitude: float,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        forecast_days: Optional[int] = 7,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetches daily weather metrics from Open-Meteo for given coordinates.

        Parameters:
            latitude: Latitude of location (e.g. 10.5276 for Thrissur)
            longitude: Longitude of location (e.g. 76.2144 for Thrissur)
            start_date: Optional start date 'YYYY-MM-DD'
            end_date: Optional end date 'YYYY-MM-DD'
            forecast_days: Number of forecast days (default 7, max 16) if date range is not specified
            timezone: Timezone for daily aggregation (default 'Asia/Kolkata')

        Returns:
            Dict containing:
                - status: 'success'
                - location: metadata (coordinates, timezone, elevation)
                - total_days: int
                - daily_forecasts: List[Dict] with normalized fields
        """
        self._validate_coordinates(latitude, longitude)

        # Variables focused strictly on agriculture, spoilage, and transport
        daily_vars = [
            "temperature_2m_max",
            "temperature_2m_min",
            "temperature_2m_mean",
            "relative_humidity_2m_mean",
            "precipitation_sum",
            "rain_sum",
            "weather_code",
        ]

        params: Dict[str, Any] = {
            "latitude": round(float(latitude), 4),
            "longitude": round(float(longitude), 4),
            "daily": ",".join(daily_vars),
            "timezone": timezone or self.default_timezone,
        }

        if start_date and end_date:
            # Validate date string formats
            try:
                datetime.strptime(start_date.strip(), "%Y-%m-%d")
                datetime.strptime(end_date.strip(), "%Y-%m-%d")
            except ValueError:
                raise WeatherError(
                    f"Invalid date format. Expected 'YYYY-MM-DD', received start_date='{start_date}', end_date='{end_date}'"
                )
            params["start_date"] = start_date.strip()
            params["end_date"] = end_date.strip()
        elif forecast_days:
            if not (1 <= int(forecast_days) <= 16):
                raise WeatherError(f"forecast_days must be between 1 and 16. Received: {forecast_days}")
            params["forecast_days"] = int(forecast_days)

        try:
            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "AgriMiniProject/1.0"},
            )
        except requests.exceptions.Timeout:
            raise WeatherAPIError(f"Open-Meteo API request timed out after {self.timeout} seconds.")
        except requests.exceptions.ConnectionError as e:
            raise WeatherAPIError(f"Connection error connecting to Open-Meteo: {e}")
        except requests.exceptions.RequestException as e:
            raise WeatherAPIError(f"Network error during Open-Meteo request: {e}")

        if response.status_code != 200:
            err_text = response.text[:200] if response.text else "No response body"
            raise WeatherAPIError(
                f"Open-Meteo API returned HTTP {response.status_code}: {err_text}"
            )

        try:
            raw_data = response.json()
        except ValueError as e:
            raise WeatherAPIError(
                f"Failed to parse JSON response from Open-Meteo: {e}. Raw content: {response.text[:200]}"
            )

        if not isinstance(raw_data, dict):
            raise WeatherAPIError(
                f"Unexpected response structure: expected JSON object, got {type(raw_data).__name__}"
            )

        # Parse and normalize daily forecast series
        daily_section = raw_data.get("daily", {})
        if not isinstance(daily_section, dict) or not daily_section.get("time"):
            raise WeatherAPIError("Open-Meteo response contains empty or missing 'daily' time series data.")

        normalized_days = self._normalize_daily_series(daily_section)

        return {
            "status": "success",
            "source": "Open-Meteo",
            "location": {
                "latitude": raw_data.get("latitude", float(latitude)),
                "longitude": raw_data.get("longitude", float(longitude)),
                "elevation": raw_data.get("elevation"),
                "timezone": raw_data.get("timezone", self.default_timezone),
            },
            "total_days": len(normalized_days),
            "daily_forecasts": normalized_days,
        }

    def _normalize_daily_series(self, daily: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Transforms columnar Open-Meteo daily arrays into a list of standardized day records."""
        times = daily.get("time", [])
        temp_max_list = daily.get("temperature_2m_max", [])
        temp_min_list = daily.get("temperature_2m_min", [])
        temp_mean_list = daily.get("temperature_2m_mean", [])
        humidity_list = daily.get("relative_humidity_2m_mean", [])
        precip_list = daily.get("precipitation_sum", [])
        rain_list = daily.get("rain_sum", [])
        weather_code_list = daily.get("weather_code", [])

        records = []
        for i in range(len(times)):
            code = weather_code_list[i] if i < len(weather_code_list) and weather_code_list[i] is not None else None
            condition = WMO_CODE_MAP.get(int(code), "Unknown") if code is not None else "N/A"

            def safe_float(arr: List[Any], idx: int) -> Optional[float]:
                if idx < len(arr) and arr[idx] is not None:
                    try:
                        return round(float(arr[idx]), 2)
                    except (ValueError, TypeError):
                        return None
                return None

            records.append({
                "date": str(times[i]),
                "temp_max_celsius": safe_float(temp_max_list, i),
                "temp_min_celsius": safe_float(temp_min_list, i),
                "temp_mean_celsius": safe_float(temp_mean_list, i),
                "humidity_mean_pct": safe_float(humidity_list, i),
                "precipitation_mm": safe_float(precip_list, i),
                "rain_mm": safe_float(rain_list, i),
                "weather_code": int(code) if code is not None else None,
                "weather_condition": condition,
            })

        return records
