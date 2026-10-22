"use client";

/** Overview lamp adapted from the original UI; see CREDITS.md. */

import { useEffect, useState } from "react";

const ACCENT = "#00e5ff";
const WCODE: Record<number, string> = { 0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle", 61: "Rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow", 75: "Snow", 80: "Showers", 81: "Showers", 82: "Showers", 95: "Storm", 96: "Storm", 99: "Storm" };

function WeatherGlyph({code}: {code: number | null}) {
  const rain = code != null && ((code >= 51 && code <= 67) || (code >= 80 && code <= 82));
  const snow = code != null && code >= 71 && code <= 77;
  const storm = code != null && code >= 95;
  const cloudy = code != null && code >= 1 && code <= 48;
  return <svg className="pao-weather-icon" viewBox="0 0 64 64" aria-hidden="true">
    <defs><filter id="weather-glow"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
    {!rain && !snow && !storm && !cloudy && <g filter="url(#weather-glow)" stroke="#f5a623" strokeWidth="2.5" strokeLinecap="round">
      <circle cx="32" cy="32" r="13" fill="#f5a623" stroke="none"/>
      {[0,45,90,135,180,225,270,315].map(angle => <line key={angle} x1="32" y1="8" x2="32" y2="14" transform={`rotate(${angle} 32 32)`}/>) }
    </g>}
    {(cloudy || rain || snow || storm) && <g filter="url(#weather-glow)">
      {code != null && code <= 2 && <circle cx="23" cy="24" r="10" fill="#f5a623"/>}
      <path d="M18 43h29c7 0 10-10 4-14-2-2-5-2-7-1-2-9-15-11-20-3-8-2-13 2-13 8 0 4 3 7 7 7Z" fill="#8cc9d7" stroke="#c6f4fb" strokeWidth="1.5"/>
      {rain && <path d="M23 49l-3 6m13-6-3 6m13-6-3 6" stroke="#00e5ff" strokeWidth="2" strokeLinecap="round"/>}
      {snow && <text x="20" y="58" fill="#d9f8ff" fontSize="15">✦ ✦</text>}
      {storm && <path d="M34 46h8l-7 8h5l-10 9 3-8h-5Z" fill="#ffd080"/>}
    </g>}
  </svg>;
}

function Clock() {
  const [now, setNow] = useState<Date | null>(null);
  const [unit, setUnit] = useState<"c" | "f">("c");
  const [wx, setWx] = useState<{ temp: number | null; code: number | null; city: string; rain: number | null; humidity: number | null; wind: number | null } | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let ok = true;
    // Via our own API route, so open-meteo never sees visitor IPs. The route
    // returns the visitor's own city + weather (Vercel geo headers).
    const load = () =>
      fetch("/api/weather")
        .then((r) => r.json())
        .then((d) => { if (ok) setWx({
          temp: d.current?.temperature_2m ?? null,
          code: d.current?.weather_code ?? null,
          city: d.city || "Hạ Long",
          rain: d.current?.precipitation_probability ?? null,
          humidity: d.current?.relative_humidity_2m ?? null,
          wind: d.current?.wind_speed_10m ?? null,
        }); })
        .catch(() => {});
    load();
    const id = setInterval(load, 1200000);
    return () => { ok = false; clearInterval(id); };
  }, []);

  if (!now) return <div style={{ height: 48 }} />;
  const time = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const date = now.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

  const shownTemp = wx?.temp == null ? null : unit === "c" ? wx.temp : wx.temp * 9 / 5 + 32;

  return (
    <div className="pao-clock-weather">
      <div className="pao-clock-block">
        <div className="pao-clock-time">{time}</div>
        <div style={{ fontSize: 10.5, letterSpacing: "0.2em", color: "rgba(240,237,232,0.55)", marginTop: 4, textTransform: "uppercase" }}>{date}</div>
      </div>
      {wx && (
        <div className="pao-weather" aria-label={`Thời tiết ${wx.city}`}>
          <WeatherGlyph code={wx.code} />
          <div className="pao-weather-reading">
            <div className="pao-weather-temperature">{shownTemp != null ? Math.round(shownTemp) : "–"}<span>°</span></div>
            <div className="pao-weather-units" aria-label="Đơn vị nhiệt độ">
              <button type="button" aria-pressed={unit === "c"} onClick={() => setUnit("c")}>C</button><i />
              <button type="button" aria-pressed={unit === "f"} onClick={() => setUnit("f")}>F</button>
            </div>
            <div className="pao-weather-place">{wx.city.toUpperCase()}{wx.code != null ? ` · ${(WCODE[wx.code] || "").toUpperCase()}` : ""}</div>
          </div>
          <div className="pao-weather-details">
            <span>Khả năng có mưa: <strong>{wx.rain ?? "–"}%</strong></span>
            <span>Độ ẩm: <strong>{wx.humidity ?? "–"}%</strong></span>
            <span>Gió: <strong>{wx.wind != null ? Math.round(wx.wind) : "–"} km/h</strong></span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PaoOverviewPanel({open, onToggle}: {open: boolean; onToggle: () => void}) {
  const FIL = 210;

  return (
    <div className={`pao-overview${open ? " is-open" : ""}`} style={{ pointerEvents: "none" }}>
      {/* downward glow cone */}
      <div style={{
        position: "absolute", top: 14, left: 8, width: "min(520px, 94vw)", height: 240, pointerEvents: "none",
        background: `radial-gradient(ellipse 48% 70% at 46% 0%, ${ACCENT}${open ? "55" : "28"}, ${ACCENT}0a 46%, transparent 72%)`,
        filter: "blur(10px)", transition: "all .5s ease",
      }} />

      {/* filament line + sliding node + click target */}
      <div
        className="pao-overview-toggle"
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
        role="button" tabIndex={0} aria-label="Mở bảng điều khiển" aria-expanded={open} aria-controls="pao-workspace-tabs"
        style={{ position: "relative", width: FIL + 12, height: 40, cursor: "pointer", pointerEvents: "auto", userSelect: "none" }}
      >
        <div style={{
          position: "absolute", top: 14, left: 8, width: FIL, height: 2, borderRadius: 2,
          background: "#a5f3fc",
          boxShadow: `0 0 10px ${ACCENT}, 0 0 26px ${ACCENT}${open ? ", 0 0 54px " + ACCENT : ""}`,
          transition: "all .5s ease",
        }} />
        {/* the node that slides to the right end when the panel opens */}
        <div style={{
          position: "absolute", top: 11, left: open ? FIL : 6, width: 8, height: 8, borderRadius: "50%",
          background: "#e0fbff", boxShadow: `0 0 10px ${ACCENT}, 0 0 18px ${ACCENT}`,
          transition: "left .5s ease", pointerEvents: "none",
        }} />
        <span style={{
          position: "absolute", top: 20, left: 10, fontFamily: "var(--font-mono)", fontSize: 13.5, letterSpacing: "0.22em",
          color: `rgba(165,243,252,${open ? 0.9 : 0.55})`, transition: "color .4s",
        }}>BẢNG ĐIỀU KHIỂN</span>
      </div>

      {/* clock + Hạ Long weather inside the lit cone */}
      <div className="pao-overview-clock" style={{ paddingLeft: 14, paddingTop: 6, width: "fit-content", pointerEvents: "auto" }}>
        <Clock />
      </div>

    </div>
  );
}
