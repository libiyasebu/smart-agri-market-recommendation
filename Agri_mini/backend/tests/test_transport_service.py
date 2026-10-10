import pytest
from unittest.mock import MagicMock
from app.services.transport_service import TransportService, DEFAULT_VEHICLE_PROFILES
from app.services.routing_service import (
    RoutingDataService,
    InvalidCoordinatesError,
    NoRouteFoundError,
    RoutingAPIError,
)
from app.schemas.transport import TransportEstimateRequest


def test_single_trip_cost_calculation():
    """Test standard single-trip logistics calculation, fuel, maintenance, per-kg and per-quintal rates."""
    service = TransportService()
    # distance = 84.0 km, quantity = 1000 kg, mini_truck (capacity=1500kg, eff=12km/L, maint=4Rs/km, driver=500Rs)
    res = service.calculate_transport_cost(
        distance_km=84.0,
        duration_minutes=80.0,
        quantity_kg=1000.0,
        vehicle_type="mini_truck",
        fuel_price_per_litre=95.0,
        toll_charges=0.0,
        other_charges=0.0,
    )

    assert res.status == "success"
    assert res.number_of_trips == 1
    assert res.distance_km == 84.0
    assert res.quantity_kg == 1000.0
    assert res.quantity_quintals == 10.0

    # Fuel: 84 / 12 = 7.0 L * 95 = 665.0 Rs
    assert res.fuel_required_litres == 7.0
    assert res.fuel_cost == 665.0

    # Maintenance: 84 * 4 = 336.0 Rs
    assert res.maintenance_cost == 336.0
    assert res.driver_cost == 500.0

    # Single trip: 665 + 336 + 500 = 1501.0 Rs
    assert res.single_trip_cost == 1501.0
    assert res.total_transport_cost == 1501.0

    # Per kg: 1501 / 1000 = 1.50 Rs/kg
    assert res.transport_cost_per_kg == 1.50
    # Per quintal: 1501 / 10 = 150.10 Rs/quintal
    assert res.transport_cost_per_quintal == 150.10


def test_multi_trip_critical_cases():
    """Test multi-trip ceil logic for exact multiples, exact boundary, and boundary+1 kg."""
    service = TransportService()
    # Case A: exactly 3000 kg with 1500 kg capacity -> exactly 2 trips
    res_3000 = service.calculate_transport_cost(
        distance_km=100.0,
        duration_minutes=90.0,
        quantity_kg=3000.0,
        vehicle_type="mini_truck",
    )
    assert res_3000.number_of_trips == 2
    assert res_3000.total_transport_cost == round(res_3000.single_trip_cost * 2, 2)

    # Case B: exact boundary 1500 kg -> 1 trip
    res_1500 = service.calculate_transport_cost(
        distance_km=100.0,
        duration_minutes=90.0,
        quantity_kg=1500.0,
        vehicle_type="mini_truck",
    )
    assert res_1500.number_of_trips == 1
    assert res_1500.total_transport_cost == res_1500.single_trip_cost

    # Case C: 1501 kg with 1500 kg capacity -> 2 trips
    res_1501 = service.calculate_transport_cost(
        distance_km=100.0,
        duration_minutes=90.0,
        quantity_kg=1501.0,
        vehicle_type="mini_truck",
    )
    assert res_1501.number_of_trips == 2
    assert res_1501.total_transport_cost == round(res_1501.single_trip_cost * 2, 2)


def test_toll_and_other_charges():
    """Test inclusion of toll gate fees and handling charges in single and total trip costs."""
    service = TransportService()
    res = service.calculate_transport_cost(
        distance_km=50.0,
        duration_minutes=45.0,
        quantity_kg=1000.0,
        vehicle_type="pickup",
        toll_charges=120.0,
        other_charges=80.0,
    )
    assert res.toll_charges == 120.0
    assert res.other_charges == 80.0
    expected_single = round(res.fuel_cost + res.maintenance_cost + res.driver_cost + 120.0 + 80.0, 2)
    assert res.single_trip_cost == expected_single


def test_all_supported_vehicle_profiles():
    """Verify all 5 vehicle profiles are supported and calculate positive realistic costs."""
    service = TransportService()
    for v_type in ["three_wheeler", "mini_truck", "pickup", "medium_truck", "large_truck"]:
        res = service.calculate_transport_cost(
            distance_km=60.0,
            duration_minutes=50.0,
            quantity_kg=500.0,
            vehicle_type=v_type,
        )
        assert res.vehicle_type == v_type
        assert res.total_transport_cost > 0
        assert res.vehicle_capacity_kg == DEFAULT_VEHICLE_PROFILES[v_type].capacity_kg


def test_three_wheeler_small_farmer_load_cheaper_than_mini_truck():
    """Verify 50 kg load on same route has lower transport cost for three_wheeler than mini_truck."""
    service = TransportService()
    dist = 50.0
    qty = 50.0

    res_auto = service.calculate_transport_cost(
        distance_km=dist,
        duration_minutes=60.0,
        quantity_kg=qty,
        vehicle_type="three_wheeler",
    )
    res_mini = service.calculate_transport_cost(
        distance_km=dist,
        duration_minutes=60.0,
        quantity_kg=qty,
        vehicle_type="mini_truck",
    )

    assert res_auto.number_of_trips == 1
    assert res_mini.number_of_trips == 1
    assert res_auto.total_transport_cost < res_mini.total_transport_cost
    assert res_auto.vehicle_display_name == "Three-Wheeler Cargo Auto"
    # Auto = 50/25*95 + 50*2 + 250 = 190 + 100 + 250 = 540.0 Rs
    assert res_auto.total_transport_cost == 540.0
    # Mini = 50/12*95 + 50*4 + 500 = 395.83 + 200 + 500 = 1095.83 Rs
    assert res_mini.total_transport_cost == 1095.83


def test_three_wheeler_capacity_and_trips():
    """Verify capacity ceil trips logic: 50kg->1 trip, 500kg->1 trip, 501kg->2 trips."""
    service = TransportService()
    res_50 = service.calculate_transport_cost(distance_km=10.0, duration_minutes=15.0, quantity_kg=50.0, vehicle_type="three_wheeler")
    assert res_50.number_of_trips == 1

    res_500 = service.calculate_transport_cost(distance_km=10.0, duration_minutes=15.0, quantity_kg=500.0, vehicle_type="three_wheeler")
    assert res_500.number_of_trips == 1

    res_501 = service.calculate_transport_cost(distance_km=10.0, duration_minutes=15.0, quantity_kg=501.0, vehicle_type="three_wheeler")
    assert res_501.number_of_trips == 2


def test_unsupported_vehicle_type_raises_error():
    """Verify unsupported vehicle types raise explicit ValueError."""
    service = TransportService()
    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(
            distance_km=50.0,
            duration_minutes=40.0,
            quantity_kg=500.0,
            vehicle_type="drone_carrier",
        )
    assert "Unsupported vehicle_type" in str(exc.value)


def test_invalid_numerical_inputs():
    """Verify negative and zero numerical inputs raise ValueError."""
    service = TransportService()
    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(distance_km=-10.0, duration_minutes=10.0, quantity_kg=100.0)
    assert "distance_km" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(distance_km=10.0, duration_minutes=10.0, quantity_kg=0.0)
    assert "quantity_kg" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(distance_km=10.0, duration_minutes=10.0, quantity_kg=100.0, fuel_price_per_litre=-10.0)
    assert "fuel_price_per_litre" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(distance_km=10.0, duration_minutes=10.0, quantity_kg=100.0, toll_charges=-5.0)
    assert "toll_charges" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        service.calculate_transport_cost(distance_km=10.0, duration_minutes=10.0, quantity_kg=100.0, other_charges=-5.0)
    assert "other_charges" in str(exc.value)


def test_mocked_routing_service_integration():
    """Test full estimation workflow with mocked OSRM routing response."""
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

    service = TransportService(routing_service=mock_routing)
    req = TransportEstimateRequest(
        origin_name="Thrissur, Kerala",
        origin_lat=10.5276,
        origin_lon=76.2144,
        destination_name="Kochi, Kerala",
        destination_lat=9.9312,
        destination_lon=76.2673,
        quantity_kg=1000.0,
        vehicle_type="mini_truck",
    )

    res = service.estimate_cost_from_coordinates(req)
    assert res.distance_km == 84.89
    assert res.estimated_duration_minutes == 82.95
    assert res.total_transport_cost > 0
    mock_routing.get_route.assert_called_once()


def test_routing_service_exception_propagation():
    """Verify that routing exceptions are properly propagated from RoutingDataService."""
    mock_routing = MagicMock(spec=RoutingDataService)
    mock_routing.get_route.side_effect = NoRouteFoundError("No drivable route")

    service = TransportService(routing_service=mock_routing)
    req = TransportEstimateRequest(
        origin_name="Island A",
        origin_lat=10.0,
        origin_lon=76.0,
        destination_name="Island B",
        destination_lat=11.0,
        destination_lon=77.0,
        quantity_kg=500.0,
    )

    with pytest.raises(NoRouteFoundError) as exc:
        service.estimate_cost_from_coordinates(req)
    assert "No drivable route" in str(exc.value)
