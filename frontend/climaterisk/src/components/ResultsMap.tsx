import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { LatLngBounds } from "leaflet";
import type { AssetImpact } from "../types";
import { money } from "../lib/format";

function riskColor(frac: number): string {
  if (frac < 0.33) return "#2f9e8f";
  if (frac < 0.66) return "#e0a32e";
  return "#e5534b";
}

function FitBounds({ impacts }: { impacts: AssetImpact[] }) {
  const map = useMap();
  useEffect(() => {
    if (impacts.length === 0) return;
    const bounds = new LatLngBounds(impacts.map((a) => [a.lat, a.lon]));
    map.fitBounds(bounds.pad(0.4), { maxZoom: 8 });
  }, [map, impacts]);
  return null;
}

export function ResultsMap({ impacts, currency }: { impacts: AssetImpact[]; currency: string }) {
  const maxEai = Math.max(1, ...impacts.map((a) => a.eai));

  return (
    <div style={{ height: 320, borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
      <MapContainer center={[20, 15]} zoom={2} scrollWheelZoom style={{ height: "100%" }}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds impacts={impacts} />
        {impacts.map((a) => {
          const frac = a.eai / maxEai;
          const color = riskColor(frac);
          return (
            <CircleMarker
              key={a.id}
              center={[a.lat, a.lon]}
              radius={6 + frac * 16}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.6, weight: 2 }}
            >
              <Tooltip>EAI: {money(a.eai, currency)}/yr</Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
