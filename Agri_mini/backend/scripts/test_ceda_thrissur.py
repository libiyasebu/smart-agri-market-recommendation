import urllib.request
import json

def get_active_port():
    for port in [8002, 8001, 8000]:
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as resp:
                if resp.status == 200:
                    return port
        except Exception:
            pass
    return 8001

def test_api():
    port = get_active_port()
    base_url = f'http://127.0.0.1:{port}'
    print(f'Testing against {base_url}...')

    payload_tomato = {
        'commodity_id': 78,
        'quantity_kg': 1000,
        'source_latitude': 10.5276,
        'source_longitude': 76.2144,
        'prediction_date': '2025-10-15',
        'candidate_markets': [
            {'market_id': 147, 'district_id': 594, 'market_name': 'Thrissur APMC (Sakthan Market)', 'destination_lat': 10.5276, 'destination_lon': 76.2144},
            {'market_id': 2152, 'district_id': 594, 'market_name': 'Chalakudy Wholesale Market', 'destination_lat': 10.3070, 'destination_lon': 76.3335},
            {'market_id': 2366, 'district_id': 594, 'market_name': 'Kunnamkulam Market', 'destination_lat': 10.6508, 'destination_lon': 76.0711},
            {'market_id': 2364, 'district_id': 594, 'market_name': 'Kodungallur Market', 'destination_lat': 10.2216, 'destination_lon': 76.1953},
        ],
        'vehicle_type': 'mini_truck',
        'fuel_price_per_litre': 95.0,
        'toll_charges': 0.0,
        'other_charges': 0.0,
        'production_cost': None,
    }

    req = urllib.request.Request(
        f'{base_url}/api/recommend/ceda',
        data=json.dumps(payload_tomato).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    print('TOMATO RECOMMENDATION API STATUS:', data['status'])
    print('Recommended Market:', data['recommended_market']['market_name'])
    print('TOPSIS Score:', data['recommended_market']['topsis_score'])
    print('Rankings count:', len(data['markets']))
    for m in data['markets']:
        print(f"  #{m['rank']} {m['market_name']}: Price=Rs {m['predicted_price_per_quintal']:.2f}, Dist={m['distance_km']:.1f}km, Freight=Rs {m['transport_cost_inr']:.2f}, Spoil={m['estimated_spoilage_pct']:.2f}%, NetReturn=Rs {m['expected_net_return_inr']:.2f}, TOPSIS={m['topsis_score']:.4f}")

    payload_banana = {
        'commodity_id': 19,
        'quantity_kg': 1000,
        'source_latitude': 10.5276,
        'source_longitude': 76.2144,
        'prediction_date': '2025-10-15',
        'candidate_markets': [
            {'market_id': 147, 'district_id': 594, 'market_name': 'Thrissur APMC (Sakthan Market)', 'destination_lat': 10.5276, 'destination_lon': 76.2144},
            {'market_id': 2366, 'district_id': 594, 'market_name': 'Kunnamkulam Market', 'destination_lat': 10.6508, 'destination_lon': 76.0711},
            {'market_id': 2364, 'district_id': 594, 'market_name': 'Kodungallur Market', 'destination_lat': 10.2216, 'destination_lon': 76.1953},
        ],
        'vehicle_type': 'mini_truck',
        'fuel_price_per_litre': 95.0,
        'toll_charges': 0.0,
        'other_charges': 0.0,
        'production_cost': None,
    }

    req2 = urllib.request.Request(
        f'{base_url}/api/recommend/ceda',
        data=json.dumps(payload_banana).encode(),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req2) as resp:
        data2 = json.loads(resp.read().decode())
    print('\nBANANA RECOMMENDATION API STATUS:', data2['status'])
    print('Recommended Market:', data2['recommended_market']['market_name'])
    print('TOPSIS Score:', data2['recommended_market']['topsis_score'])
    print('Rankings count:', len(data2['markets']))
    for m in data2['markets']:
        print(f"  #{m['rank']} {m['market_name']}: Price=Rs {m['predicted_price_per_quintal']:.2f}, Dist={m['distance_km']:.1f}km, Freight=Rs {m['transport_cost_inr']:.2f}, Spoil={m['estimated_spoilage_pct']:.2f}%, NetReturn=Rs {m['expected_net_return_inr']:.2f}, TOPSIS={m['topsis_score']:.4f}")

if __name__ == '__main__':
    test_api()
