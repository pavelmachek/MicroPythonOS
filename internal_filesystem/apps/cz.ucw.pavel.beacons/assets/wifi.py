#!/usr/bin/python3
import dbus
import time

NM_BUS = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
NM_IFACE = "org.freedesktop.NetworkManager"
DEV_IFACE = "org.freedesktop.NetworkManager.Device.Wireless"

bus = dbus.SystemBus()

nm = bus.get_object(NM_BUS, NM_PATH)
nm_iface = dbus.Interface(nm, NM_IFACE)

# Get all devices
devices = nm_iface.GetDevices()

wifi_device = None

for d in devices:
    dev_obj = bus.get_object(NM_BUS, d)
    dev_props = dbus.Interface(dev_obj, "org.freedesktop.DBus.Properties")

    dev_type = dev_props.Get(NM_IFACE + ".Device", "DeviceType")

    # 2 = Wi-Fi device
    if dev_type == 2:
        wifi_device = dev_obj
        break

if not wifi_device:
    raise Exception("No Wi-Fi device found")

wifi_props = dbus.Interface(wifi_device, "org.freedesktop.DBus.Properties")
wifi_iface = dbus.Interface(wifi_device, DEV_IFACE)

# Request scan (may require permission / root depending on setup)
wifi_iface.RequestScan({})

print("Scanning...")
time.sleep(3)

def decode_ssid(ssid):
    try:
        return bytes(ssid).decode("utf-8", errors="ignore")
    except:
        return "<hidden>"

def format_bssid(bssid):
    if not bssid:
        return "<unknown>"

    try:
        return ":".join("{:02x}".format(int(b)) for b in bssid)
    except Exception:
        return "<invalid>"

def flags_to_security(wpa, rsn):
    """
    Very practical interpretation (not exhaustive spec decoding).
    """
    if wpa == 0 and rsn == 0:
        return "OPEN"

    security = []

    # WPA (legacy)
    if wpa != 0:
        security.append("WPA")

    # RSN = WPA2/WPA3 family
    if rsn != 0:
        security.append("WPA2/WPA3")

    # Heuristic for enterprise vs personal
    # (bit 0x2 often indicates IEEE 802.1X / enterprise usage)
    if (wpa & 0x2) or (rsn & 0x2):
        security.append("ENTERPRISE")
    else:
        security.append("PERSONAL")

    return "+".join(security)

def scan(wifi_props):
    # Get access points
    aps = wifi_props.Get(DEV_IFACE, "AccessPoints")
    results = []

    for ap_path in aps:
        ap = bus.get_object(NM_BUS, ap_path)
        ap_props = dbus.Interface(ap, "org.freedesktop.DBus.Properties")

        #print(ap_props)
        AP_IFACE = "org.freedesktop.NetworkManager.AccessPoint"
        ssid = ap_props.Get(AP_IFACE, "Ssid")
        strength = int(ap_props.Get(AP_IFACE, "Strength"))

        #bssid = ap_props.Get(AP_IFACE, "Bssid")
        bssid_raw = ap_props.Get(AP_IFACE, "HwAddress")
        bssid = bssid_raw # format_bssid(bssid_raw)

        #bssid = b""
        freq = ap_props.Get(AP_IFACE, "Frequency")
        last_seen = ap_props.Get(AP_IFACE, "LastSeen")
        mode = ap_props.Get(AP_IFACE, "Mode")

        wpa = ap_props.Get(AP_IFACE, "WpaFlags")
        rsn = ap_props.Get(AP_IFACE, "RsnFlags")

        name = decode_ssid(ssid)
        security = flags_to_security(wpa, rsn)

        results.append({
            "ssid": name,
            "bssid": bssid,
            "strength": int(strength),
            "freq": int(freq),
            "last_seen": int(last_seen),
            "mode": int(mode),
            "security": security
        })

    # sort by signal strength
    results.sort(key=lambda x: x["strength"], reverse=True)

    return results


# -----------------------------
# Display
# -----------------------------

def print_aps(aps):
    print("\n=== Wi-Fi Networks ===")
    for ap in aps:
        print(
            f"{ap['ssid']:<25} "
            f"{ap['strength']:>3}% "
            f"{ap['freq']:>4}MHz "
            f"{ap['bssid']} "
            f"{ap['security']:<15}  "
            f"last_seen={ap['last_seen']}"
        )

aps = scan(wifi_props)
print_aps(aps)
