from custom_components.ha_lightning import binary_sensor


def test_haversine_same_point():
    d = binary_sensor._haversine_km(0, 0, 0, 0)
    assert abs(d) < 1e-6


def test_haversine_known_distance():
    # distance between Paris (48.8566 N, 2.3522 E) and London (51.5074 N, -0.1278 W)
    paris_lat, paris_lon = 48.8566, 2.3522
    london_lat, london_lon = 51.5074, -0.1278
    d = binary_sensor._haversine_km(paris_lat, paris_lon, london_lat, london_lon)
    # approx 343 km
    assert 330 < d < 360
