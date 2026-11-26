// Google Maps JS API (via @vis.gl/react-google-maps) with Advanced Markers and a deck.gl overlay for
// the heat layer and transfer routes. Google's own HeatmapLayer was removed from the Maps JS API in
// May 2026, so deck.gl's HeatmapLayer is used through GoogleMapsOverlay. Without a browser key the
// same props render on Leaflet + OpenStreetMap so the demo never breaks.
import { useEffect, useMemo } from "react";
import { APIProvider, AdvancedMarker, Map as GMap, useMap } from "@vis.gl/react-google-maps";
import { GoogleMapsOverlay } from "@deck.gl/google-maps";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { ArcLayer } from "@deck.gl/layers";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";

export type Marker = { id: number | string; lat: number; lng: number; color: string; label: string; size?: number; shape?: string };
export type HeatPoint = { lat: number; lng: number; weight: number };
export type Route = { from: [number, number]; to: [number, number]; color?: string; label?: string };
type Props = {
  markers: Marker[]; heat?: HeatPoint[]; routes?: Route[]; showHeat?: boolean; showRoutes?: boolean;
  onMarkerClick?: (id: Marker["id"]) => void; onMapClick?: (lat: number, lng: number) => void; height?: number;
  center?: [number, number]; zoom?: number; pick?: [number, number] | null;
};

const KEY = import.meta.env.VITE_MAPS_BROWSER_KEY as string | undefined;
const MAP_ID = (import.meta.env.VITE_MAPS_MAP_ID as string | undefined) || "DEMO_MAP_ID";
const CENTER: [number, number] = [28.62, 77.21];

export const mapsProvider = KEY ? "Google Maps Platform" : "OpenStreetMap (fallback - set VITE_MAPS_BROWSER_KEY)";

export default function MapView(props: Props) {
  return KEY ? <GoogleMapView {...props} /> : <LeafletMapView {...props} />;
}

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function DeckOverlay({ heat, routes, showHeat, showRoutes }: Pick<Props, "heat" | "routes" | "showHeat" | "showRoutes">) {
  const map = useMap();
  const overlay = useMemo(() => new GoogleMapsOverlay({ layers: [] }), []);
  useEffect(() => {
    if (!map) return;
    overlay.setMap(map);
    return () => overlay.setMap(null);
  }, [map, overlay]);
  useEffect(() => {
    overlay.setProps({
      layers: [
        showHeat && heat?.length
          ? new HeatmapLayer<HeatPoint>({ id: "risk-heat", data: heat, getPosition: (d) => [d.lng, d.lat], getWeight: (d) => d.weight, radiusPixels: 70, intensity: 1.2, threshold: 0.03 })
          : null,
        showRoutes && routes?.length
          ? new ArcLayer<Route>({ id: "routes", data: routes, getSourcePosition: (d) => [d.from[1], d.from[0]], getTargetPosition: (d) => [d.to[1], d.to[0]],
              getSourceColor: (d) => hexToRgb(d.color ?? "#0072B2"), getTargetColor: (d) => hexToRgb(d.color ?? "#0072B2"), getWidth: 3, getHeight: 0.4 })
          : null,
      ].filter(Boolean),
    });
  }, [overlay, heat, routes, showHeat, showRoutes]);
  return null;
}

function GoogleMapView({ markers, heat, routes, showHeat = true, showRoutes = true, onMarkerClick, onMapClick, height = 520, center = CENTER, zoom = 11, pick }: Props) {
  return (
    <APIProvider apiKey={KEY!}>
      <div style={{ height }} className="overflow-hidden rounded-xl border border-slate-200">
        <GMap mapId={MAP_ID} defaultCenter={{ lat: center[0], lng: center[1] }} defaultZoom={zoom} gestureHandling="greedy" disableDefaultUI={false}
          onClick={(e) => e.detail.latLng && onMapClick?.(e.detail.latLng.lat, e.detail.latLng.lng)}>
          {markers.map((m) => (
            <AdvancedMarker key={m.id} position={{ lat: m.lat, lng: m.lng }} title={m.label} onClick={() => onMarkerClick?.(m.id)}>
              <div className="flex items-center justify-center rounded-full border-2 border-white text-[10px] font-bold text-white shadow"
                style={{ background: m.color, width: m.size ?? 18, height: m.size ?? 18 }}>{m.shape ?? ""}</div>
            </AdvancedMarker>
          ))}
          {pick && <AdvancedMarker position={{ lat: pick[0], lng: pick[1] }} title="Incident"><div className="text-2xl">💥</div></AdvancedMarker>}
          <DeckOverlay heat={heat} routes={routes} showHeat={showHeat} showRoutes={showRoutes} />
        </GMap>
      </div>
    </APIProvider>
  );
}

function ClickCatcher({ onMapClick }: { onMapClick?: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onMapClick?.(e.latlng.lat, e.latlng.lng) });
  return null;
}

function LeafletMapView({ markers, heat, routes, showHeat = true, showRoutes = true, onMarkerClick, onMapClick, height = 520, center = CENTER, zoom = 11, pick }: Props) {
  const maxW = Math.max(1, ...(heat ?? []).map((h) => h.weight));
  return (
    <div style={{ height }} className="overflow-hidden rounded-xl border border-slate-200">
      <MapContainer center={center} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <ClickCatcher onMapClick={onMapClick} />
        {showHeat && heat?.map((h, i) => (
          <CircleMarker key={`h${i}`} center={[h.lat, h.lng]} radius={12 + 30 * (h.weight / maxW)} pathOptions={{ stroke: false, fillColor: "#D55E00", fillOpacity: 0.12 + 0.3 * (h.weight / maxW) }} />
        ))}
        {showRoutes && routes?.map((r, i) => (
          <Polyline key={`r${i}`} positions={[r.from, r.to]} pathOptions={{ color: r.color ?? "#0072B2", weight: 3, dashArray: "6 6" }}>
            {r.label && <Tooltip sticky>{r.label}</Tooltip>}
          </Polyline>
        ))}
        {markers.map((m) => (
          <CircleMarker key={m.id} center={[m.lat, m.lng]} radius={(m.size ?? 18) / 2.2} eventHandlers={{ click: () => onMarkerClick?.(m.id) }}
            pathOptions={{ color: "#fff", weight: 2, fillColor: m.color, fillOpacity: 0.95 }}>
            <Tooltip>{m.label}</Tooltip>
          </CircleMarker>
        ))}
        {pick && <CircleMarker center={pick} radius={10} pathOptions={{ color: "#000", fillColor: "#000", fillOpacity: 0.8 }}><Tooltip permanent>Incident</Tooltip></CircleMarker>}
      </MapContainer>
    </div>
  );
}
