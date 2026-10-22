export type Theme = 'dark' | 'light';
export type ThemePreference = Theme | 'auto';
export const THEME_KEY: string;
export const THEME_BOOTSTRAP: string;
export function validTheme(value: unknown): value is ThemePreference;
export function resolveTheme(preference: ThemePreference, now?: Date): Theme;
export function millisecondsUntilThemeChange(now?: Date): number;
export function watchAutoTheme(onChange: (theme: Theme) => void, clock?: {
  now?: () => Date;
  setTimeout?: (callback: () => void, delay: number) => unknown;
  clearTimeout?: (handle: unknown) => void;
}): {refresh: () => void; stop: () => void};
export function readTheme(storage: Pick<Storage,'getItem'> | null, fallback?: ThemePreference): ThemePreference;
export function saveTheme(storage: Pick<Storage,'setItem'> | null, value: unknown): boolean;
