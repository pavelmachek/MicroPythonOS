import ujson

# -----------------------------
# WEATHER DATA MODEL
# -----------------------------

class WData:
    WMO_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        56: "Freezing drizzle",
        57: "Freezing drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Freezing rain",
        67: "Freezing rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Rain showers",
        81: "Rain showers",
        82: "Heavy rain showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm + hail",
        99: "Thunderstorm + hail",
    }

    def init(self):
        pass

    def code_to_text(self, code):
        return self.WMO_CODES.get(int(code), "Unknown")

    def get(self, v, cw, ind):
        if ind == None:
            return cw[v]
        else:
            return cw[v][ind]

    def full(self):
        return f"{self.code}\nTemp {self.temp:.1f} dew {self.dew:.1f} pres {self.pres:1f}\n" \
               f"Precip {self.precip}\nWind {self.wind} gust {self.gust}"
        
    def short(self):
        r = f"{self.code} {self.temp:.1f}°C"
        if self.dew + 3 > self.temp:
            r += f" dew {self.dew:.1f}°C"
        if self.gust > self.wind + 5:
            r += f" {self.gust:.0f} g"
        elif self.wind > 10:
            r += f" {self.wind:.0f} w"
        # FIXME: add precip
        return r

    def similar(self, prev):
        if self.code != prev.code:
            return False
        if abs(self.temp - prev.temp) > 3:
            return False
        if abs(self.wind - prev.wind) > 10:
            return False
        if abs(self.gust - prev.gust) > 10:
            return False
        return True

    def summarize(self):
        return self.ftime() + self.short()
    
class Hourly(WData):
    def init(self, cw, ind):
        super().init()
        self.time = None
        self.temp   = self.get("temperature_2m", cw, ind)
        self.dew    = self.get("dewpoint_2m", cw, ind)
        self.pres   = self.get("pressure_msl", cw, ind)
        self.precip = self.get("precipitation", cw, ind)
        self.wind   = self.get("wind_speed_10m", cw, ind)
        self.gust   = self.get("wind_gusts_10m", cw, ind)
        self.raw_code = self.get("weather_code", cw, ind)
        self.code = self.code_to_text(self.raw_code)

    def ftime(self):
        if self.time:
            return self.time[11:13] + "h "
        return ""

class Daily(WData):
    def init(self, cw, ind):
        super().init()
        self.temp       = self.get("temperature_2m_max", cw, ind)
        self.temp_min   = self.get("temperature_2m_min", cw, ind)
        self.dew        = self.get("dewpoint_2m_max", cw, ind)
        self.dew_min    = self.get("dewpoint_2m_min", cw, ind)
        self.pres       = None
        self.precip     = self.get("precipitation_sum", cw, ind)
        self.wind       = self.get("wind_speed_10m_max", cw, ind)
        self.gust       = self.get("wind_gusts_10m_max", cw, ind)
        self.raw_code   = self.get("weather_code", cw, ind)
        self.code = self.code_to_text(self.raw_code)

    def ftime(self):
        return self.time[8:10] + ". "

class Weather:
    name = "Prague"
    # LKPR airport
    lat = 50 + 6/60.
    lon = 14 + 15/60.
    
    def __init__(self):
        self.now = None
        self.hourly = []
        self.daily = []
        self.summary = "(no weather)"

    def fetch(self):
        self.summary = "...fetching..."

        # See https://open-meteo.com/en/docs?forecast_days=1&current=relative_humidity_2m
        
        host = "api.open-meteo.com"
        path = (
            "/v1/forecast?"
            "latitude={}&longitude={}"
            "&current=temperature_2m,dewpoint_2m,pressure_msl,precipitation,weather_code,wind_speed_10m,wind_gusts_10m"
            "&forecast_hours=8"
            "&hourly=temperature_2m,dewpoint_2m,pressure_msl,precipitation,weather_code,wind_speed_10m,wind_gusts_10m"
	    "&forecast_days=10"
	    "&daily=temperature_2m_max,temperature_2m_min,dewpoint_2m_min,dewpoint_2m_max,pressure_msl_min,pressure_msl_max,precipitation_sum,weather_code,wind_speed_10m_max,wind_gusts_10m_max"
            "&timezone=auto"
        ).format(self.lat, self.lon)

        print("Weather fetch: ", path)
        data = self.download_url("https://"+host+path)
        if not data:
            self.summary = "Download error"
            return
        
        #print("Have result:", body.decode())

        # Parse JSON
        data = ujson.loads(data)

        # ---- Extract data ----
        print("\n\n")

        s = ""

        print("---- ")
        cw = data["current"]
        self.now = Hourly()
        self.now.init(cw, None)
        prev = self.now
        t = self.now.summarize()
        s += t + "\n"
        print(t)

        self.hourly = []
        d = data["hourly"]
        times = d["time"]
        #print(d)

        print("---- ")
        for i in range(len(times)):
            h = Hourly()
            h.init(d, i)
            h.time = times[i]
            self.hourly.append(h)
            if not h.similar(prev):
                t = h.summarize()
                s += t + "\n"
                print(t)
                prev = h

        self.daily = []
        d = data["daily"]
        times = d["time"]
        #print(d)

        print("---- ")
        for i in range(len(times)):
            h = Daily()
            h.init(d, i)
            h.time = times[i]
            self.daily.append(h)
            if i == 0:
                prev = h
            elif not h.similar(prev):
                t = h.summarize()
                s += t + "\n"
                print(t)
                prev = h


        self.summary = s

    def summarize_future():
        now = utime.time()

        # Rain detection in next 24h
        for h in weather.hourly[:24]:
            if h["precip"] >= 1.0:
                return "Rain soon"

        # Temperature trend
        if len(weather.hourly) > 24:
            t0 = weather.hourly[0]["temp"]
            t24 = weather.hourly[24]["temp"]
            if abs(t24 - t0) < 2:
                return "No change expected"
            if t24 > t0:
                return "Getting warmer"
            else:
                return "Getting cooler"

        return "Stable weather"
            
