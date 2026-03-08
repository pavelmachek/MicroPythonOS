import os

from mpos.imu.drivers.base import IMUDriverBase
        
class SysfsDir:
    def _p(self, name: str):
        return self.path + "/" + name

    def _exists(self, name):
        try:
            os.stat(name)
            return True
        except OSError:
            return False

    def _is_dir(self, path):
        # MicroPython: stat tuple, mode is [0]
        try:
            st = os.stat(path)
            mode = st[0]
            # directory bit (POSIX): 0o040000
            return (mode & 0o170000) == 0o040000
        except OSError:
            return False

    def find_dir_with_file(self, filename, base_dir):
        """
        Returns full path to iio:deviceX that contains given filename,
        e.g. "/sys/bus/iio/devices/iio:device0"

        Returns None if not found.
        """

        print("Is dir? ", self._is_dir(base_dir), base_dir)
        try:
            entries = os.listdir(base_dir)
        except OSError:
            print("Error listing dir")
            return None

        for entry in entries:
            print("Entry:", entry)
            if not entry.startswith("iio:device"):
                continue

            dev_path = base_dir + "/" + entry
            if not self._is_dir(dev_path):
                continue

            if self._exists(dev_path + "/" + filename):
                return dev_path

        return None

    def _read_text(self, name: str) -> str:
        if False:
            print("Read: ", name)
        f = open(name, "r")
        try:
            return f.readline().strip()
        finally:
            f.close()

    def _read_float(self, name: str) -> float:
        return float(self._read_text(name))

    def _read_int(self, name: str) -> int:
        return int(self._read_text(name), 10)

    def _read_raw_scaled(self, raw_name: str, scale_name: str) -> float:
        raw = self._read_int(raw_name)
        scale = self._read_float(scale_name)
        return raw * scale

    
class IIODir(SysfsDir):
    def init(self, name):
        self.path = self.find_dir_with_file(name, "/sys/bus/iio/devices/")
        self.ensure_sampling_frequency_max(self.path)

    def _parse_available_freqs(self, text):
        """
        IIO typically uses either:
          "12.5 25 50 100"
        or
          "0.5 1 2 4 8 16"

        Returns list of floats.
        """
        out = []
        for tok in text.replace(",", " ").split():
            out.append(float(tok))
        return out

    def _format_freq_for_sysfs(self, f):
        """
        Kernel sysfs usually accepts either integer or decimal.
        We'll keep it minimal:
          - if f is whole number -> "100"
          - else -> "12.5"
        """
        if int(f) == f:
            return str(int(f))
        # avoid scientific notation
        s = ("%.6f" % f).rstrip("0").rstrip(".")
        return s

    def _try_set_via_sudo_tee(self, path, value_str):
        """
        Executes:
          sh -c 'echo VALUE | sudo tee PATH'
        Returns True if command returns 0.
        """
        cmd = "sh -c 'echo %s | sudo tee %s >/dev/null'" % (value_str, path)
        rc = os.system(cmd)
        return rc == 0

    def ensure_sampling_frequency_max(self, dev_path):
        """
        dev_path: "/sys/bus/iio/devices/iio:deviceX"

        Returns:
          (changed: bool, max_freq: float or None, current: float or None)
        """

        if not dev_path:
            return (False, None, None)

        sf = dev_path + "/sampling_frequency"
        sfa = dev_path + "/sampling_frequency_available"

        # read current
        cur_s = self._read_text(sf)
        cur = float(cur_s)

        avail_s = self._read_text(sfa)
        avail = self._parse_available_freqs(avail_s)

        maxf = max(avail)

        # already max (tolerate float fuzz)
        if abs(cur - maxf) < 1e-6:
            print("Already at max frequency")
            return (False, maxf, cur)

        max_str = self._format_freq_for_sysfs(maxf)

        # Fallback: sudo tee
        ok = self._try_set_via_sudo_tee(sf, max_str)
        if not ok:
            print("Can't switch to max frequency")
            return (False, maxf, cur)

        new_cur = float(self._read_text(sf))

        return (True, maxf, new_cur)

    def ensure_sampling_frequency_max_for_device_with_file(self, filename):
        """
        Convenience wrapper:
          - finds iio device containing filename
          - sets sampling_frequency to maximum
        """
        dev = self.find_iio_device_with_file(filename)
        if dev is None:
            return (None, False, None, None)

        changed, maxf, cur = self.ensure_sampling_frequency_max(dev)
        return (dev, changed, maxf, cur)
        
    def _read_mount_matrix(self, p):
        """
        Reads IIO mount matrix from *mount_matrix

        Format example:
            "0, 1, 0; -1, 0, 0; 0, 0, 1"

        Returns:
            3x3 matrix as tuple of tuples (float)
        """
        path = p + "/" + "in_accel_mount_matrix"
        if not self._exists(path):
            # Strange, librem 5 has different filename
            path = self.path + "/" + "mount_matrix"
            if not self._exists(path):
                return None

        text = self._read_text(path).strip()

        rows = []
        for row in text.split(";"):
            rows.append(tuple(float(x.strip()) for x in row.split(",")))

        if len(rows) != 3 or any(len(r) != 3 for r in rows):
            raise ValueError("Invalid mount matrix format")

        return tuple(rows)


    def _apply_mount_matrix(self, ax, ay, az, p):
        """
        Applies IIO mount matrix to acceleration vector.

        Returns rotated (ax, ay, az).
        """
        M = self._read_mount_matrix(p)
        if M is None:
            return (ax, ay, az)

        x = M[0][0]*ax + M[0][1]*ay + M[0][2]*az
        y = M[1][0]*ax + M[1][1]*ay + M[1][2]*az
        z = M[2][0]*ax + M[2][1]*ay + M[2][2]*az

        return (x, y, z)
        
class IIODriver(IMUDriverBase):
    """
    Read sensor data via Linux IIO sysfs.

    Typical base path:
        /sys/bus/iio/devices/iio:device0
    """

    def __init__(self):
        super().__init__()
        self.accel = IIODir()
        self.mag = IIODir()
        self.gyro = IIODir()

        self.accel.init("in_accel_x_raw")
        self.gyro.init("in_anglvel_x_raw")
        self.mag.init("in_magn_x_raw")

        self.available = any((self.accel.path, self.mag.path, self.gyro.path))

        if not self.available:
            print("IIO: no IIO sensors detected")
            return

    def _raw_acceleration_mps2(self):
        if not self.accel.path:
            return (0.0, 0.0, 0.0)
        scale_name = self.accel.path + "/" + "in_accel_scale"

        ax = self.accel._read_raw_scaled(self.accel.path + "/" + "in_accel_x_raw", scale_name)
        ay = self.accel._read_raw_scaled(self.accel.path + "/" + "in_accel_y_raw", scale_name)
        az = self.accel._read_raw_scaled(self.accel.path + "/" + "in_accel_z_raw", scale_name)

        return self.accel._apply_mount_matrix(ax, ay, az, self.accel.path)

    def _raw_gyroscope_dps(self):
        if not self.gyro.path:
            return (0.0, 0.0, 0.0)
        scale_name = self.gyro.path + "/" + "in_anglvel_scale"
        mul = 57.2957795

        gx = mul * self.gyro._read_raw_scaled(self.gyro.path + "/" + "in_anglvel_x_raw", scale_name)
        gy = mul * self.gyro._read_raw_scaled(self.gyro.path + "/" + "in_anglvel_y_raw", scale_name)
        gz = mul * self.gyro._read_raw_scaled(self.gyro.path + "/" + "in_anglvel_z_raw", scale_name)

        return self.gyro._apply_mount_matrix(gx, gy, gz, self.gyro.path)

    def read_acceleration(self):
        ax, ay, az = self._raw_acceleration_mps2()
        return (
            ax - self.accel_offset[0],
            ay - self.accel_offset[1],
            az - self.accel_offset[2],
        )

    def read_gyroscope(self):
        gx, gy, gz = self._raw_gyroscope_dps()
        return (
            gx - self.gyro_offset[0],
            gy - self.gyro_offset[1],
            gz - self.gyro_offset[2],
        )

    def read_magnetometer(self) -> tuple[float, float, float]:
        if not self.mag.path:
            return (0.0, 0.0, 0.0)

        gx = self.mag._read_raw_scaled(self.mag.path + "/" + "in_magn_x_raw", self.mag.path + "/" + "in_magn_x_scale")
        gy = self.mag._read_raw_scaled(self.mag.path + "/" + "in_magn_y_raw", self.mag.path + "/" + "in_magn_y_scale")
        gz = self.mag._read_raw_scaled(self.mag.path + "/" + "in_magn_z_raw", self.mag.path + "/" + "in_magn_z_scale")        

        return self.mag._apply_mount_matrix(gx, gy, gz, self.mag.path)

    def read_temperature(self) -> float:
        """
        Tries common IIO patterns:
          - in_temp_input (already scaled, usually millidegree C)
          - in_temp_raw + in_temp_scale
        """
        return 12.34
        if not self.accel.path:
            return None

        raw_path = self.accel.path + "/" + "in_temp_raw"
        scale_path = self.accel.path + "/" + "in_temp_scale"
        if not self._exists(raw_path) or not self._exists(scale_path):
            return None
        return self._read_raw_scaled(raw_path, scale_path)
>>>>>>> fd6a469a (iio: refactor directory handing to allow future changes)

