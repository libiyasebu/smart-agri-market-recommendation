import pytest
from datetime import date
from unittest.mock import MagicMock
from app.services.spoilage_service import SpoilageService, DEFAULT_PERISHABILITY_PROFILES
from app.services.routing_service import (
    RoutingDataService,
    InvalidCoordinatesError,
    NoRouteFoundError,
    RoutingAPIError,
)
from app.services.weather_service import WeatherDataService, WeatherAPIError
from app.schemas.spoilage import SpoilageEstimateRequest


def test_supported_commodity_profile_resolution():
    """Verify all core agricultural commodities resolve correctly."""
    service = SpoilageService()
    for name in ["Tomato", "tomato", "Onion", "Potato", "Banana", "Cabbage", "Green Chilli", "chilli"]:
        profile = service.resolve_commodity_profile(name)
        assert profile is not None
        assert profile.base_perishability_score > 0
        assert profile.max_loss_potential_pct > 0


def test_unsupported_commodity_raises_error():
    """Verify unsupported commodity raises explicit ValueError."""
    service = SpoilageService()
    with pytest.raises(ValueError) as exc:
        service.resolve_commodity_profile("DragonFruitExotic")
    assert "Unsupported commodity" in str(exc.value)


def test_deterministic_calculation_same_inputs_same_output():
    """Verify calculation is strictly deterministic."""
    service = SpoilageService()
    res1 = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=84.89,
        duration_minutes=82.95,
        temp_mean_c=28.0,
        temp_max_c=32.0,
        humidity_pct=85.0,
        precipitation_mm=5.0,
    )
    res2 = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=84.89,
        duration_minutes=82.95,
        temp_mean_c=28.0,
        temp_max_c=32.0,
        humidity_pct=85.0,
        precipitation_mm=5.0,
    )
    assert res1.risk_score == res2.risk_score
    assert res1.estimated_spoilage_pct == res2.estimated_spoilage_pct
    assert res1.risk_level == res2.risk_level


def test_risk_score_and_spoilage_pct_within_valid_bounds():
    """Verify risk scores and loss percentages are bounded between 0 and 100 across extreme test inputs."""
    service = SpoilageService()
    # Extreme low
    res_low = service.calculate_spoilage_risk(
        commodity="Potato",
        distance_km=10.0,
        duration_minutes=15.0,
        temp_mean_c=15.0,
        temp_max_c=18.0,
        humidity_pct=65.0,
        precipitation_mm=0.0,
    )
    assert 0.0 <= res_low.risk_score <= 100.0
    assert 0.0 <= res_low.estimated_spoilage_pct <= 100.0

    # Extreme high
    res_high = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=800.0,
        duration_minutes=720.0,  # 12 hours
        temp_mean_c=42.0,
        temp_max_c=46.0,
        humidity_pct=95.0,
        precipitation_mm=40.0,
    )
    assert 0.0 <= res_high.risk_score <= 100.0
    assert 0.0 <= res_high.estimated_spoilage_pct <= 100.0


def test_longer_transit_duration_increases_or_maintains_risk():
    """Verify monotonicity: increasing transit duration holding all else constant increases risk."""
    service = SpoilageService()
    res_short = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=50.0,
        duration_minutes=45.0,
        temp_mean_c=28.0,
        temp_max_c=32.0,
        humidity_pct=80.0,
    )
    res_long = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=300.0,
        duration_minutes=300.0,
        temp_mean_c=28.0,
        temp_max_c=32.0,
        humidity_pct=80.0,
    )
    assert res_long.risk_score > res_short.risk_score
    assert res_long.estimated_spoilage_pct > res_short.estimated_spoilage_pct
    assert res_long.risk_factors.transit_time_stress > res_short.risk_factors.transit_time_stress


def test_higher_ambient_heat_increases_risk():
    """Verify that excessive ambient temperature increases thermal stress and overall risk."""
    service = SpoilageService()
    res_cool = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=100.0,
        duration_minutes=90.0,
        temp_mean_c=18.0,  # Within optimal range (12-22°C)
        temp_max_c=21.0,
        humidity_pct=75.0,
    )
    res_hot = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=100.0,
        duration_minutes=90.0,
        temp_mean_c=36.0,  # Substantial heat excess
        temp_max_c=40.0,
        humidity_pct=75.0,
    )
    assert res_hot.risk_score > res_cool.risk_score
    assert res_hot.risk_factors.temperature_stress > res_cool.risk_factors.temperature_stress


def test_humidity_sensitive_commodity_reactions():
    """Verify that high humidity increases moisture stress for sensitive commodities."""
    service = SpoilageService()
    res_opt = service.calculate_spoilage_risk(
        commodity="Onion",
        distance_km=60.0,
        duration_minutes=60.0,
        temp_mean_c=22.0,
        temp_max_c=25.0,
        humidity_pct=65.0,
    )
    res_humid = service.calculate_spoilage_risk(
        commodity="Onion",
        distance_km=60.0,
        duration_minutes=60.0,
        temp_mean_c=22.0,
        temp_max_c=25.0,
        humidity_pct=98.0,  # Causes rot/sprouting risk in onion
    )
    assert res_humid.risk_factors.humidity_stress > res_opt.risk_factors.humidity_stress


def test_risk_level_classification_ranges():
    """Verify correct classification across all 4 risk tiers."""
    service = SpoilageService()

    # 1. LOW (Score <= 25)
    res_low = service.calculate_spoilage_risk(
        commodity="Potato",
        distance_km=20.0,
        duration_minutes=20.0,
        temp_mean_c=16.0,
        temp_max_c=19.0,
        humidity_pct=60.0,
    )
    assert res_low.risk_level == "LOW"

    # 2. MODERATE (25 < Score <= 50)
    res_mod = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=85.0,
        duration_minutes=83.0,
        temp_mean_c=26.0,
        temp_max_c=30.0,
        humidity_pct=85.0,
    )
    assert res_mod.risk_level == "MODERATE"

    # 3. HIGH (50 < Score <= 75)
    res_high = service.calculate_spoilage_risk(
        commodity="Tomato",
        distance_km=250.0,
        duration_minutes=240.0,
        temp_mean_c=35.0,
        temp_max_c=39.0,
        humidity_pct=90.0,
    )
    assert res_high.risk_level == "HIGH"

    # 4. VERY HIGH (Score > 75)
    res_vhigh = service.calculate_spoilage_risk(
        commodity="Banana",
        distance_km=600.0,
        duration_minutes=600.0,
        temp_mean_c=42.0,
        temp_max_c=46.0,
        humidity_pct=95.0,
        precipitation_mm=25.0,
    )
    assert res_vhigh.risk_level == "VERY HIGH"


def test_mocked_osrm_and_weather_orchestration():
    """Test full estimation workflow with mocked OSRM routing and Open-Meteo weather."""
    mock_routing = MagicMock(spec=RoutingDataService)
    mock_routing.get_route.return_value = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 84.89,
        "duration_minutes": 82.95,
        "duration_hours": 1.38,
        "origin": {"latitude": 10.5276, "longitude": 76.2144},
        "destination": {"latitude": 9.9312, "longitude": 76.2673},
    }

    mock_weather = MagicMock(spec=WeatherDataService)
    mock_weather.fetch_weather.return_value = {
        "status": "success",
        "daily_forecasts": [
            {
                "date": "2026-08-28",
                "temp_mean_celsius": 26.5,
                "temp_max_celsius": 30.2,
                "humidity_mean_pct": 82.0,
                "precipitation_mm": 2.5,
                "rain_mm": 2.5,
            }
        ]
    }

    service = SpoilageService(routing_service=mock_routing, weather_service=mock_weather)
    req = SpoilageEstimateRequest(
        commodity="Tomato",
        origin_name="Thrissur, Kerala",
        origin_lat=10.5276,
        origin_lon=76.2144,
        destination_name="Kochi, Kerala",
        destination_lat=9.9312,
        destination_lon=76.2673,
        transport_date=date(2026, 8, 28),
    )

    res = service.estimate_spoilage_from_coordinates(req, db=None)
    assert res.commodity == "Tomato"
    assert res.distance_km == 84.89
    assert res.transit_duration_minutes == 82.95
    assert res.weather.temperature_mean_c == 26.5
    assert res.weather.humidity_pct == 82.0
    assert res.weather_source == "live_api"
    assert res.weather_matched is True
    assert res.risk_score > 0
    assert res.estimated_spoilage_pct > 0


def test_weather_fallback_when_services_fail():
    """Verify that when weather DB and live API fail, default fallback is applied gracefully without crashing."""
    mock_routing = MagicMock(spec=RoutingDataService)
    mock_routing.get_route.return_value = {
        "status": "success",
        "provider": "OSRM (OpenStreetMap)",
        "distance_km": 50.0,
        "duration_minutes": 45.0,
        "duration_hours": 0.75,
    }

    mock_weather = MagicMock(spec=WeatherDataService)
    mock_weather.fetch_weather.side_effect = WeatherAPIError("Open-Meteo down")

    service = SpoilageService(routing_service=mock_routing, weather_service=mock_weather)
    req = SpoilageEstimateRequest(
        commodity="Tomato",
        origin_name="Thrissur",
        origin_lat=10.5276,
        origin_lon=76.2144,
        destination_name="Kochi",
        destination_lat=9.9312,
        destination_lon=76.2673,
        transport_date=date(2026, 8, 28),
    )

    res = service.estimate_spoilage_from_coordinates(req, db=None)
    assert res.weather_source == "configured_fallback"
    assert res.weather_matched is False
    assert res.weather.temperature_mean_c == 28.5
    assert res.risk_score > 0
