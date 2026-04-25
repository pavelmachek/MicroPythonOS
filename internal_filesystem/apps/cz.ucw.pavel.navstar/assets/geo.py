import math

def knots_to_kmh(knots):
    return knots * 1.852

def deg_to_rad(d):
    return d * math.pi / 180.0


def rad_to_deg(r):
    return r * 180.0 / math.pi


def haversine_km(lat1, lon1, lat2, lon2):
    # Great-circle distance
    R = 6371.0088
    phi1 = deg_to_rad(lat1)
    phi2 = deg_to_rad(lat2)
    dphi = deg_to_rad(lat2 - lat1)
    dl = deg_to_rad(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def bearing_deg(lat1, lon1, lat2, lon2):
    # Initial bearing from point1 -> point2
    phi1 = deg_to_rad(lat1)
    phi2 = deg_to_rad(lat2)
    dl = deg_to_rad(lon2 - lon1)

    y = math.sin(dl) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dl)
    br = math.atan2(y, x)
    brd = (rad_to_deg(br) + 360.0) % 360.0
    return brd





