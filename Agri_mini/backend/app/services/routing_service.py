import requests
from typing import Dict, Any, List, Optional
from app.config import settings


class RoutingError(Exception):
    """Base exception for routing data acquisition errors."""
    pass


class InvalidCoordinatesError(RoutingError):
    """Raised when latitude or longitude coordinates are out of valid bounds."""
    pass


class NoRouteFoundError(RoutingError):
    """Raised when OSRM cannot compute a driving route between coordinates."""
    pass


class RoutingAPIError(RoutingError):
    """Raised when the OSRM service returns an HTTP error, times out, or fails."""
    pass


class RoutingDataService:
    """Service to calculate and normalize road routes, driving distances, and durations from OSRM/OpenStreetMap."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        profile: str = "driving",
        timeout: int = 15,
    ):
        self.base_url = (base_url or settings.OSRM_BASE_URL).rstrip("/")
        self.profile = profile
        self.timeout = timeout

    def _validate_coordinates(self, lat: float, lon: float, label: str = "Coordinate") -> None:
        """Validates geographic latitude and longitude bounds."""
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise InvalidCoordinatesError(
                f"{label} coordinates must be numeric values. Received lat={lat!r}, lon={lon!r}"
            )
        if not (-90.0 <= float(lat) <= 90.0):
            raise InvalidCoordinatesError(
                f"{label} latitude {lat} is out of valid range [-90.0, 90.0]."
            )
        if not (-180.0 <= float(lon) <= 180.0):
            raise InvalidCoordinatesError(
                f"{label} longitude {lon} is out of valid range [-180.0, 180.0]."
            )

    def get_route(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        overview: str = "full",
        geometries: str = "geojson",
    ) -> Dict[str, Any]:
        """
        Calculates road driving route between origin and destination using OSRM.

        Parameters:
            origin_lat: Origin latitude (e.g. 10.5276 for Thrissur)
            origin_lon: Origin longitude (e.g. 76.2144 for Thrissur)
            dest_lat: Destination latitude (e.g. 9.9312 for Kochi)
            dest_lon: Destination longitude (e.g. 76.2673 for Kochi)
            overview: Detail level ('full', 'simplified', 'false')
            geometries: Format of geometry ('geojson' or 'polyline')

        Returns:
            Dict containing:
                - status: 'success'
                - provider: 'OSRM (OpenStreetMap)'
                - origin: Dict with latitude and longitude
                - destination: Dict with latitude and longitude
                - distance_km: float (road distance in km)
                - duration_minutes: float (travel duration in minutes)
                - duration_hours: float (travel duration in hours)
                - geometry: Dict with GeoJSON type and coordinates list
        """
        self._validate_coordinates(origin_lat, origin_lon, label="Origin")
        self._validate_coordinates(dest_lat, dest_lon, label="Destination")

        # OSRM path coordinate format: {longitude},{latitude};{longitude},{latitude}
        coords_str = f"{origin_lon:.6f},{origin_lat:.6f};{dest_lon:.6f},{dest_lat:.6f}"
        endpoint_url = f"{self.base_url}/route/v1/{self.profile}/{coords_str}"

        params: Dict[str, Any] = {
            "overview": overview,
            "geometries": geometries,
            "steps": "false",
            "annotations": "false",
        }

        try:
            response = requests.get(
                endpoint_url,
                params=params,
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "AgriMiniProject/1.0"},
            )
        except requests.exceptions.Timeout:
            raise RoutingAPIError(f"OSRM API request timed out after {self.timeout} seconds for endpoint '{endpoint_url}'.")
        except requests.exceptions.ConnectionError as e:
            raise RoutingAPIError(f"Connection error reaching OSRM service at '{self.base_url}': {e}")
        except requests.exceptions.RequestException as e:
            raise RoutingAPIError(f"Network request error during OSRM route calculation: {e}")
        except Exception as e:
            raise RoutingAPIError(f"Unexpected error during route calculation: {e}")

        if response.status_code != 200:
            err_text = response.text[:200] if response.text else "No response body"
            raise RoutingAPIError(
                f"OSRM API returned HTTP {response.status_code}: {err_text}"
            )

        try:
            raw_data = response.json()
        except ValueError as e:
            raise RoutingAPIError(
                f"Failed to parse JSON response from OSRM: {e}. Raw body: {response.text[:200]}"
            )

        if not isinstance(raw_data, dict):
            raise RoutingAPIError(
                f"Unexpected response structure from OSRM: expected JSON object, got {type(raw_data).__name__}"
            )

        osrm_code = raw_data.get("code")
        if osrm_code != "Ok":
            message = raw_data.get("message", "No message provided")
            if osrm_code == "NoRoute":
                raise NoRouteFoundError(
                    f"No drivable road route found between Origin ({origin_lat}, {origin_lon}) "
                    f"and Destination ({dest_lat}, {dest_lon}). Message: {message}"
                )
            raise RoutingAPIError(f"OSRM error code '{osrm_code}': {message}")

        routes = raw_data.get("routes", [])
        if not routes or not isinstance(routes, list):
            raise NoRouteFoundError("OSRM response contains empty 'routes' list.")

        primary_route = routes[0]
        distance_meters = primary_route.get("distance")
        duration_seconds = primary_route.get("duration")

        if distance_meters is None or duration_seconds is None:
            raise RoutingAPIError("OSRM primary route is missing 'distance' or 'duration' fields.")

        geometry_obj = primary_route.get("geometry", {})
        geometry_type = geometry_obj.get("type", "LineString") if isinstance(geometry_obj, dict) else "LineString"
        coordinates_list = geometry_obj.get("coordinates", []) if isinstance(geometry_obj, dict) else []

        distance_km = round(float(distance_meters) / 1000.0, 2)
        duration_minutes = round(float(duration_seconds) / 60.0, 2)
        duration_hours = round(float(duration_seconds) / 3600.0, 2)

        return {
            "status": "success",
            "provider": "OSRM (OpenStreetMap)",
            "origin": {
                "latitude": round(float(origin_lat), 6),
                "longitude": round(float(origin_lon), 6),
            },
            "destination": {
                "latitude": round(float(dest_lat), 6),
                "longitude": round(float(dest_lon), 6),
            },
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "duration_hours": duration_hours,
            "geometry": {
                "type": geometry_type,
                "coordinates": coordinates_list,
                "total_points": len(coordinates_list),
            },
        }
