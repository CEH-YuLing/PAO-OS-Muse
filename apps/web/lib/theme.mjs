export const THEME_KEY = 'pao.ui.theme';
export function validTheme(value) { return value === 'light' || value === 'dark' || value === 'auto'; }
// Use the device's local wall clock, not UTC or the operating-system theme.
export function resolveTheme(preference, now = new Date()) {
  if (preference === 'light' || preference === 'dark') return preference;
  const hour = now.getHours();
  return preference === 'auto' && hour >= 6 && hour < 18 ? 'light' : 'dark';
}
export function millisecondsUntilThemeChange(now = new Date()) {
  const next = new Date(now.getTime());
  const hour = now.getHours();
  if (hour < 6) next.setHours(6, 0, 0, 0);
  else if (hour < 18) next.setHours(18, 0, 0, 0);
  else { next.setDate(next.getDate() + 1); next.setHours(6, 0, 0, 0); }
  const delay = next.getTime() - now.getTime();
  return Number.isFinite(delay) && delay > 0 ? delay : 60_000;
}
// A bounded wall-clock recheck also handles sleep, DST and clock/timezone edits.
// Inject the clock in tests; never change the user's Windows clock to test it.
export function watchAutoTheme(onChange, clock = {}) {
  const now = clock.now || (() => new Date());
  const schedule = clock.setTimeout || ((fn, delay) => globalThis.setTimeout(fn, delay));
  const cancel = clock.clearTimeout || (id => globalThis.clearTimeout(id));
  let timer;
  let stopped = false;
  const refresh = () => {
    if (stopped) return;
    if (timer !== undefined) cancel(timer);
    const instant = now();
    onChange(resolveTheme('auto', instant));
    timer = schedule(refresh, Math.min(millisecondsUntilThemeChange(instant), 60_000));
  };
  refresh();
  return {refresh, stop() { stopped = true; if (timer !== undefined) cancel(timer); }};
}
export function readTheme(storage, fallback = 'dark') {
  try { const value = storage?.getItem(THEME_KEY); return validTheme(value) ? value : fallback; }
  catch { return fallback; }
}
export function saveTheme(storage, value) {
  if (!validTheme(value)) return false;
  try { storage?.setItem(THEME_KEY, value); return true; } catch { return false; }
}
export const THEME_BOOTSTRAP = `(function(){var p='dark';try{var v=localStorage.getItem('pao.ui.theme');if(v==='light'||v==='dark'||v==='auto')p=v}catch(e){}var h=new Date().getHours(),t=p==='auto'?(h>=6&&h<18?'light':'dark'):p;document.documentElement.dataset.themePreference=p;document.documentElement.dataset.theme=t;document.documentElement.style.colorScheme=t})()`;
