#!/usr/bin/env python3
from pydbus import SystemBus
import pydbus
import time
import sys
import json

"""
Librem 5, phosh, python. Give me code to read current battery level.

(and more)

Lets make it class Phone, one method would be reading battery information, one would be reading operator name / signal strength, one would be getting wifi enabled/disabled / AP name.

Can you also get silent mode, pending notifications, and gps coordinates on request?

run this with sudo to work around permission problems

sudo apt install python3-pydbus
"""



class Phone:
    verbose = False

    def __init__(self):
        self.bus = pydbus.SystemBus()
        self.sess = pydbus.SessionBus()

    # --- Battery ---
    def get_battery_info(self):
        upower = self.bus.get("org.freedesktop.UPower")
        for dev_path in upower.EnumerateDevices():
            if self.verbose: print("dev_path is", dev_path)
            dev = self.bus.get(".UPower", dev_path)
            if dev.Type == 2:  # battery
                return {
                    "percentage": dev.Percentage,
                    "state": dev.State,
                    "charging": dev.State == 1,
                    "time_to_empty": dev.TimeToEmpty,  # seconds, 0 if unknown
                    "time_to_full": dev.TimeToFull,    # seconds, 0 if unknown
                }
        return None

    # --- Vibration ---
    # https://github.com/agx/feedbackd/blob/main/examples/example.py
    def set_vibration(self, enable: bool):
        # Connect to GSettings backend (org.gnome.SettingsDaemon, commonly)
        dconf = self.sess.get("org.sigxcpu.Feedback", "/org/sigxcpu/Feedback")

        # Use the standard Properties interface
        iface = dconf["org.sigxcpu.Feedback.Haptic"]

        # Example pattern: list of (duration, strength)
        pattern = [
            (3.0, 1),
            (1.0, 200),
            (0.0, 50),
            (0.5, 300),
        ]

        iface.Vibrate("org.foo.app", pattern)
        print(dir(iface))

    # --- Feedback: silent/full/... ---
    # broken
    def set_feedback_theme(self, value):
        # Connect to GSettings backend (org.gnome.SettingsDaemon, commonly)
        dconf = self.bus.get("org.gnome.SettingsDaemon", "/org/gnome/SettingsDaemon/Dbus")

        # Use the standard Properties interface
        iface = dconf["org.freedesktop.DBus.Properties"]

        # Set the key (schema, key, value)
        # GVariant format: value must match the expected type, here 's' = string
        from gi.repository import GLib
        value = GLib.Variant("s", "custom")

        iface.Set("org.sigxcpu.feedbackd", "theme", value)

    # --- Mobile network ---
    # Untested / broken
    def get_mobile_info(self):
        mm = self.bus.get("org.freedesktop.ModemManager1")
        for modem_path in mm.GetManagedObjects():
            modem = self.bus.get(".ModemManager1", modem_path)
            operator = getattr(modem.Modem3gpp, "OperatorName", None)
            signal = None
            try:
                signal = modem.Signal.Get()["rssi"]
            except Exception as e:
                return {"error": str(e)}
            return {"operator": operator, "signal_strength": signal}
        return None

    # --- WiFi ---
    def get_wifi_info(self):
        nm = self.bus.get("org.freedesktop.NetworkManager")
        wifi_enabled = nm.WirelessEnabled
        active_ssid = None
        for conn_path in nm.ActiveConnections:
            ac = self.bus.get(".NetworkManager", conn_path)
            if ac.Type == "802-11-wireless":
                # Step 1: get the settings connection path
                settings_path = ac.Connection
                # Step 2: fetch the settings object
                sc = self.bus.get(".NetworkManager", settings_path)
                settings = sc.GetSettings()
                ssid = settings["802-11-wireless"]["ssid"]
                if isinstance(ssid, (bytes, bytearray)):
                    ssid = ssid.decode("utf-8", errors="ignore")
                else:
                    ssid = ''.join(chr(c) for c in ssid)
                return {"enabled": nm.WirelessEnabled, "ssid": ssid}

        return {"enabled": wifi_enabled, "ssid": active_ssid}

    # --- Silent mode / Do Not Disturb ---
    # broken
    def get_silent_mode(self):
        try:
            portal = self.bus.get("org.freedesktop.portal.Desktop",
                                  "/org/freedesktop/portal/desktop")
            return portal.Settings.Read("org.freedesktop.appearance",
                                        "sound-theme-enabled") == 0
        except Exception as e:
            return {"error": str(e)}

    # --- Pending notifications ---
    # broken
    def get_notifications(self):
        try:
            notif = self.bus.get("org.freedesktop.Notifications")
            # org.freedesktop.Notifications has no standard "list" API,
            # Phosh implements its own.
            # In phosh, you can query /org/gnome/Notifications for backlog.
            phosh_notif = self.bus.get("org.gnome.Shell",
                                       "/org/gnome/Shell/Notifications")
            return phosh_notif.ListNotifications()
        except Exception as e:
            return {"error": str(e)}

    # --- GPS coordinates ---
    # Needs permissions from .desktop
    def get_location(self):
        try:
            geoclue = self.bus.get("org.freedesktop.GeoClue2",
                                   "/org/freedesktop/GeoClue2/Manager")
            # Step 1: get a client object path
            client_path = geoclue.GetClient()
            client = self.bus.get("org.freedesktop.GeoClue2", client_path)

            # Step 2: set required properties
            client.DesktopId = "phone.py"
            client.RequestedAccuracyLevel = 3  # 3 = city-level accuracy
            client.Start()  # start location updates

            # Step 3: read location
            loc_path = client.Location
            location = self.bus.get("org.freedesktop.GeoClue2", loc_path)

            return {
                "latitude": location.Latitude,
                "longitude": location.Longitude,
                "accuracy": location.Accuracy,
            }
        except Exception as e:
            return {"error": str(e)}

    # --- Hardware sensors (accelerometer, gyroscope, light, proximity) ---
    def get_hardware_sensors(self):
        try:
            obj = self.bus.get("net.hadess.SensorProxy", "/net/hadess/SensorProxy")

            # obj exposes multiple interfaces; access the one we need
            sensor_proxy = obj["net.hadess.SensorProxy"]

            # Enable accelerometer
            sensor_proxy.ClaimAccelerometer()
            sensor_proxy.ClaimLight()
            sensor_proxy.ClaimProximity()

            # Give it a small delay to start updating
            time.sleep(0.5)

            sensors = {}
            #print(dir(sensor_proxy))
            print('tilt -- tells you phone position -- ', sensor_proxy.AccelerometerTilt)
            print('orient -- orientation for screen rotation -- ', sensor_proxy.AccelerometerOrientation)
            
            # Ambient light
            if sensor_proxy.HasAmbientLight:
                sensors['ambient_light'] = {
                    'lux': sensor_proxy.LightLevel
                }

            # Proximity
            if sensor_proxy.HasProximity:
                sensors['proximity'] = {
                    'near': sensor_proxy.ProximityNear
                }

            return sensors
        except Exception as e:
            return {"error": str(e)}

    # --- Screen lock ---
    def get_screen_lock(self):
        # This one complains 
        #screensaver = self.sess.get("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver")
        screensaver = self.sess.get("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver")
        print(dir(screensaver))
        #screensaver.SetActive(True)
        return { "Locked": screensaver.GetActive() }


# bus = SystemBus()
# login1 = bus.get("org.freedesktop.login1", "/org/freedesktop/login1")
# login1.Suspend(False)  # False = interactive, True = force
# login1.Hibernate(False)

phone = Phone()
if sys.argv[1] == "bat":
    print(json.dumps(phone.get_battery_info()))
    sys.exit(0)

def full():
    print("Battery:", phone.get_battery_info())
    phone.set_vibration(True)
#    print("Mobile:", phone.get_mobile_info())
    print("WiFi:", phone.get_wifi_info())
#    print("Silent mode:", phone.get_silent_mode())
#    print("Notifications:", phone.get_notifications())
#    print("Location:", phone.get_location())
    print("Hardware sensors:", phone.get_hardware_sensors())
    print("Screen lock:", phone.get_screen_lock())
    phone.set_vibration(False)
    # full, quiet, silent
#    phone.set_feedback_theme("full")
