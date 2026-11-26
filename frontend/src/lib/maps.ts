export const MAPS_KEY = import.meta.env.VITE_MAPS_BROWSER_KEY as string | undefined;
export const mapsProvider = MAPS_KEY ? "Google Maps Platform" : "OpenStreetMap (fallback - set VITE_MAPS_BROWSER_KEY)";
