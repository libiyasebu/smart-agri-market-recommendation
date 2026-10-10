import pytest
from unittest.mock import patch, MagicMock
from app.services.routing_service import (
    RoutingDataService,
    InvalidCoordinatesError,
    NoRouteFoundError,
    RoutingAPIError,
)


def test_invalid_coordinates_raise_error():
    service = RoutingDataService()

    # Latitude out of bounds
    with pytest.raises(InvalidCoordinatesError) as exc:
        service.get_route(origin_lat=95.0, origin_lon=76.21, dest_lat=9.93, dest_lon=76.26)
    assert "Origin latitude 95.0 is out of valid range" in str(exc.value)

    # Destination Longitude out of bounds
    with pytest.raises(InvalidCoordinatesError) as exc:
        service.get_route(origin_lat=10.52, origin_lon=76.21, dest_lat=9.93, dest_lon=190.0)
    assert "Destination longitude 190.0 is out of valid range" in str(exc.value)

    # Non-numeric input
    with pytest.raises(InvalidCoordinatesError) as exc:
        service.get_route(origin_lat="invalid", origin_lon=76.21, dest_lat=9.93, dest_lon=76.26)  # type: ignore
    assert "must be numeric values" in str(exc.value)


def test_successful_route_normalization():
    mock_payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 84893.0,  # meters
                "duration": 4977.1,   # seconds
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [76.214365, 10.527607],
                        [76.214369, 10.527627],
                        [76.267300, 9.931200],
                    ],
                },
            }
        ],
        "waypoints": [
            {"location": [76.214365, 10.527607], "name": "Thrissur Road"},
            {"location": [76.267300, 9.931200], "name": "Kochi Road"},
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    service = RoutingDataService()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = service.get_route(
            origin_lat=10.5276,
            origin_lon=76.2144,
            dest_lat=9.9312,
            dest_lon=76.2673,
        )

        assert result["status"] == "success"
        assert result["provider"] == "OSRM (OpenStreetMap)"
        assert result["origin"]["latitude"] == 10.5276
        assert result["origin"]["longitude"] == 76.2144
        assert result["destination"]["latitude"] == 9.9312
        assert result["destination"]["longitude"] == 76.2673

        # Distance: 84893 / 1000 = 84.89 km
        assert result["distance_km"] == 84.89
        # Duration: 4977.1 / 60 = 82.95 minutes
        assert result["duration_minutes"] == 82.95
        assert result["duration_hours"] == 1.38

        # Geometry
        geom = result["geometry"]
        assert geom["type"] == "LineString"
        assert geom["total_points"] == 3
        assert geom["coordinates"][0] == [76.214365, 10.527607]
        assert geom["coordinates"][-1] == [76.267300, 9.931200]

        # Verify call URL structure (OSRM uses lon,lat;lon,lat)
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "76.214400,10.527600;76.267300,9.931200" in args[0]


def test_no_route_found_error():
    mock_payload = {
        "code": "NoRoute",
        "message": "Impossible route between points across water body without ferry",
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_payload

    service = RoutingDataService()

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(NoRouteFoundError) as exc:
            service.get_route(origin_lat=10.5276, origin_lon=76.2144, dest_lat=0.0, dest_lon=0.0)
        assert "No drivable road route found" in str(exc.value)


def test_http_500_error_handling():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    service = RoutingDataService()

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(RoutingAPIError) as exc:
            service.get_route(origin_lat=10.5276, origin_lon=76.2144, dest_lat=9.9312, dest_lon=76.2673)
        assert "HTTP 500" in str(exc.value)


def test_timeout_handling():
    service = RoutingDataService()

    with patch("requests.get", side_effect=Exception("Connection timed out")):
        with pytest.raises(RoutingAPIError) as exc:
            service.get_route(origin_lat=10.5276, origin_lon=76.2144, dest_lat=9.9312, dest_lon=76.2673)
        assert "route calculation" in str(exc.value)
