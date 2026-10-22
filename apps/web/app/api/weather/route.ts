import { NextResponse } from "next/server";

/** Current weather for Hạ Long, Quảng Ninh via Open-Meteo. */
export const dynamic = "force-dynamic";

const HA_LONG = {
  city: "Hạ Long",
  latitude: 20.950452,
  longitude: 107.073361,
};

export async function GET() {

  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${HA_LONG.latitude}&longitude=${HA_LONG.longitude}&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&hourly=precipitation_probability&forecast_days=1&timezone=Asia%2FBangkok`;
    // Cache for 10 minutes to avoid unnecessary upstream requests.
    const r = await fetch(url, { next: { revalidate: 600 } });
    if (!r.ok) throw new Error(`Open-Meteo returned ${r.status}`);
    const d = await r.json();
    const current = d.current ? {...d.current} : null;
    if (current && Array.isArray(d.hourly?.time) && Array.isArray(d.hourly?.precipitation_probability)) {
      const currentHour = String(current.time).slice(0, 13);
      const index = d.hourly.time.findIndex((time: string) => String(time).slice(0, 13) === currentHour);
      current.precipitation_probability = index >= 0 ? d.hourly.precipitation_probability[index] : null;
    }
    return NextResponse.json({ current, city: HA_LONG.city });
  } catch {
    return NextResponse.json({ current: null, city: HA_LONG.city });
  }
}
