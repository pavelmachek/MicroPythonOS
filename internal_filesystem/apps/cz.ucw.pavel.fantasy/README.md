* Fantasy phone

Fantasy consoles (such as Tic-80) are very useful for easy game
development. And I want a fantasy phone! It should be a simple
touchscreen phone, so it would be feasible to implement on hardware
such as esp32 + cellphone module. I hope that is possible way to phone
that would be comfortably small, perhaps around 60 grams.

But... I don't have access to such hardware now. But still I'd like to
write software for it... hence this.

* Basics

touchscreen
blit image
pcm recording/playback
battery status

get text input
http access -- requests

* Phone specific

GPS
cell 

vibration
LEDs
camera
wifi

bluetooth, nfc
sensors -- accelerometer, magnetometer, gyroscope, light sensor, proximity sensor

temperature

* Android specific

wake up

* Android limits

can't get access to hw buttons
can't blink button backlight
limits on wifi scans
can't do stuff like phone calls with audio injected to it

* PyTry

    def get_time(self):
        """
        Returns current time.

        :return: int (0-86399) - Seconds since the start of the day.
        """
        return MainActivity.get_time()

    def display_debug(self, text):
        """
        Displays a text string in the debug overlay on the device screen.

        :param text: str - The text to display.
        """
        MainActivity.display_debug(str(text))

    def get_touch_event(self):
        """
        Returns coordinates of the last touch event.

        :return: (float, float) or None - (x, y) normalized coordinates (0.0 to 1.0),
                 or None if no touch is occurring.
        """
        return MainActivity.get_touch_event()

    def get_canvas_size(self):
        """
        Returns the physical size of the canvas on the screen.

        :return: (int, int) - (width, height) in pixels.
        """
        return MainActivity.get_canvas_size()

    def blit(self, canvas, width, height):
        """
        Copies raw RGB888 pixel data to the screen bitmap.

        :param canvas: bytearray/bytes - RGB888 data (3 bytes per pixel).
        :param width: int - Width of the image data.
        :param height: int - Height of the image data.
        """
        MainActivity.blit_rgb888(bytes(canvas), int(width), int(height))

    def beep(self, freq, vol, dur):
        """
        Plays a synthetic sine wave tone.

        :param freq: float - Frequency in Hz (e.g., 440.0).
        :param vol: float - Volume (0.0 to 1.0).
        :param dur: int - Duration in milliseconds.
        """
        MainActivity.beep(float(freq), float(vol), int(dur))

    def vibrate(self, dur_ms):
        """
        Vibrates the device.

        :param dur_ms: int - Duration in milliseconds.
        """
        MainActivity.vibrate(int(dur_ms))

    def get_battery_info(self):
        """
        Returns current battery status.

        :return: (float, float, float, str, str, str) -
                 (percentage, voltage_v, temperature_c, charge_mode, status, health).
                 charge_mode: "AC", "USB", "Wireless", or "".
                 status: "Charging", "Discharging", "Full", "Not Charging", "Unknown".
                 health: "Cold", "Dead", "Good", "Overheat", "Over Voltage", "Unknown", "Failure".
        """
        return MainActivity.get_battery_info()

    def set_torch(self, enabled):
        """
        Controls the camera LED torch.

        :param enabled: bool - True to turn on, False to turn off.
        """
        MainActivity.set_torch(bool(enabled))

    def wake_up(self):
        """
        Turns the screen on and attempts to dismiss the keyguard.
        """
        MainActivity.wake_up()

    def start_gps(self):
        """
        Starts requesting GPS location and NMEA sentence updates.
        Requires location permissions to be granted.
        """
        MainActivity.start_gps()

    def stop_gps(self):
        """
        Stops all GPS and NMEA updates.
        """
        MainActivity.stop_gps()

    def get_nmea_sentences(self):
        """
        Retrieves all NMEA sentences accumulated since the last call.

        :return: str - A single string containing all NMEA sentences.
        """
        return MainActivity.get_nmea_sentences()

    def get_network_info(self):
        """
        Returns basic network and SIM operator information.

        :return: (str, str, str, str, int, str) -
                 (mcc, mnc, operator_name, sim_name, signal_dbm, data_status).
                 data_status: "Connected", "Connecting", "Disconnected", "Suspended", "Unknown".
        """
        return MainActivity.get_network_info()

    def set_notification_mode(self, mode, volume_percent=50):
        """
        Sets the device's ringer/notification mode.

        :param mode: int - 0: Silent, 1: Vibrate, 2: Normal.
        :param volume_percent: int - Volume (0 to 100) when mode is Normal.
        """
        MainActivity.set_notification_mode(int(mode), int(volume_percent))

    def set_radio_enabled(self, enabled):
        """
        Attempts to toggle cellular radio (currently a placeholder).

        :param enabled: bool - True to enable, False to disable.
        """
        MainActivity.set_radio_enabled(bool(enabled))

    def make_call(self, number):
        """
        Opens the system dialer with the specified phone number pre-filled.
        Requires manual confirmation by the user.

        :param number: str - The phone number to dial.
        """
        MainActivity.make_call(str(number))

    def send_sms(self, number, message):
        """
        Opens the system SMS application with number and message pre-filled.
        Requires manual confirmation by the user.

        :param number: str - The recipient's phone number.
        :param message: str - The message body.
        """
        MainActivity.send_sms(str(number), str(message))

    def set_wifi_enabled(self, enabled):
        """Toggles Wi-Fi on or off."""
        MainActivity.set_wifi_enabled(bool(enabled))

    def get_wifi_info(self):
        """Returns current Wi-Fi connection info (ssid, status, signal, ip)."""
        return MainActivity.get_wifi_info()

    def get_wifi_scan_results(self):
        """Returns list of nearby APs: [(ssid, level, bssid, freq), ...]."""
        return MainActivity.get_wifi_scan_results()

* PyEye

 /**
     * This method can be called from Python to display an RGBA8888 image.
     */
    fun displayImage(data: ByteArray, width: Int, height: Int) {
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val buffer = ByteBuffer.wrap(data)
        bitmap.copyPixelsFromBuffer(buffer)
        runOnUiThread {
            _pythonBitmap.value = bitmap
        }
    }

    /**
     * This method can be called from Python to get the latest camera frame.
     * Returns an array containing [width, height, rgba_data] or null.
     */
    fun getLatestFrame(): Array<Any>? {

activity.cameraPower(True)
activity.setCamera(is_front)

touch = activity.getTouch()
        if touch is not None:
            # touch contains [x, y] in normalized coordinates (0..1)
            target_x_norm = touch[0]
            target_y_norm = touch[1]

frame_info = activity.getLatestFrame()

activity.displayImage(bytes(data), width, height)

main() function, gets activity as a parameter

fun pythonPrint(message: String) {
  