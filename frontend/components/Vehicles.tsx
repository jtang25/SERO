"use client";

import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  useCallback,
} from "react";
import { Map } from "react-map-gl";
import DeckGL from "@deck.gl/react";
import { TripsLayer } from "@deck.gl/geo-layers";
import { PolygonLayer, IconLayer } from "@deck.gl/layers";
import type { Position } from "@deck.gl/core";

import {
  type FleetType,
  type TripPoint,
  type Trip,
  type GridCell,
  type StationInput,
  type StationDeployment,
  type Station,
  type DeploymentResponse,
  type RiskApiCell,
} from "../types/vehicles";
import type { ChatContext } from "../types/chat";
import {
  FIRE_STATION_INPUTS,
  POLICE_STATION_INPUTS,
} from "../data/stations";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN as string;
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const GRID_MIN_LAT = 47.48;
const GRID_MAX_LAT = 47.75;
const GRID_MIN_LON = -122.45;
const GRID_MAX_LON = -122.22;
const GRID_LAT_STEP = 0.01;
const GRID_LON_STEP = 0.01;

const SAMPLE_TRIPS: Trip[] = [
  {
    id: "veh_101",
    fleet_type: "fire",
    type: "fire_truck",
    side: "friendly",
    path: [
      { time: 0, lon: -122.345, lat: 47.6 },
      { time: 60, lon: -122.34, lat: 47.605 },
      { time: 120, lon: -122.335, lat: 47.61 },
      { time: 180, lon: -122.33, lat: 47.615 },
    ],
  },
];

type TripWithMeta = Trip & {
  fromStationId?: string;
  toStationId?: string;
  fromStationName?: string;
  toStationName?: string;
};

type StationWithFlag = Station & { inMove?: boolean };

function interpolatePosition(path: TripPoint[], t: number): [number, number] {
  if (path.length === 0) return [0, 0];
  if (t <= path[0].time) return [path[0].lon, path[0].lat];
  if (t >= path[path.length - 1].time)
    return [path[path.length - 1].lon, path[path.length - 1].lat];

  for (let i = 0; i < path.length - 1; i++) {
    const p0 = path[i];
    const p1 = path[i + 1];
    if (t >= p0.time && t <= p1.time) {
      const ratio = (t - p0.time) / (p1.time - p0.time);
      const lon = p0.lon + (p1.lon - p0.lon) * ratio;
      const lat = p0.lat + (p1.lat - p0.lat) * ratio;
      return [lon, lat];
    }
  }
  return [path[0].lon, path[0].lat];
}

function riskToColor(risk: number): [number, number, number, number] {
  if (risk < 0.15) return [0, 0, 0, 0];
  if (risk < 0.4) return [255, 255, 0, 120];
  if (risk < 0.7) return [255, 165, 0, 170];
  return [255, 0, 0, 210];
}

function latLonToCellId(lat: number, lon: number): number | null {
  const nLat = Math.ceil((GRID_MAX_LAT - GRID_MIN_LAT) / GRID_LAT_STEP);
  const nLon = Math.ceil((GRID_MAX_LON - GRID_MIN_LON) / GRID_LON_STEP);
  const i = Math.floor((lat - GRID_MIN_LAT) / GRID_LAT_STEP);
  const j = Math.floor((lon - GRID_MIN_LON) / GRID_LON_STEP);
  if (i < 0 || j < 0 || i >= nLat || j >= nLon) return null;
  return i * nLon + j;
}

function fleetPathColor(fleet: FleetType): [number, number, number] {
  return fleet === "fire" ? [255, 120, 120] : [80, 160, 255];
}

function formatTimeSeconds(t: number) {
  const total = Math.max(0, Math.floor(t));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

type LayerKey = "heatmap" | "vehicles" | "vehicleIcons" | "stations";

type LayerConfig = {
  key: LayerKey;
  label: string;
  visible: boolean;
};

type VehiclesMapProps = {
  style?: CSSProperties;
  fireStations?: StationInput[];
  policeStations?: StationInput[];
  onContextChange?: (context: ChatContext) => void;
};

export default function VehiclesMap({
  style,
  fireStations,
  policeStations,
  onContextChange,
}: VehiclesMapProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  const [gridCells, setGridCells] = useState<GridCell[]>([]);
  const [trips, setTrips] = useState<TripWithMeta[] | null>(null);
  const [stations, setStations] = useState<StationWithFlag[]>([]);

  const [isSatellite, setIsSatellite] = useState(true);
  const [isTilted, setIsTilted] = useState(true);

  const [viewState, setViewState] = useState({
    longitude: -122.335,
    latitude: 47.615,
    zoom: 11,
    pitch: 45,
    bearing: 0,
  });

  const [selectedTripId, setSelectedTripId] = useState<string | null>(null);
  const [selectedStationId, setSelectedStationId] = useState<string | null>(
    null
  );
  const [selectedCellId, setSelectedCellId] = useState<number | null>(null);

  const [controlsCollapsed, setControlsCollapsed] = useState(false);

  const [popupPos, setPopupPos] = useState({ x: 24, y: 96 });
  const [isDraggingPopup, setIsDraggingPopup] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const [layerPanelOpen, setLayerPanelOpen] = useState(false);
  const [layerConfig, setLayerConfig] = useState<LayerConfig[]>([
    { key: "heatmap", label: "Risk grid", visible: true },
    { key: "vehicles", label: "Vehicle paths", visible: true },
    { key: "vehicleIcons", label: "Vehicle icons", visible: true },
    { key: "stations", label: "Stations", visible: true },
  ]);

  useEffect(() => {
    async function fetchRisk() {
      try {
        const res = await fetch(`${API_BASE}/risk/latest`);
        if (!res.ok) {
          throw new Error(`/risk/latest failed: ${res.status} ${res.statusText}`);
        }
        const data: RiskApiCell[] = await res.json();

        const halfLat = GRID_LAT_STEP / 2;
        const halfLon = GRID_LON_STEP / 2;

        const cells: GridCell[] = data.map((row) => {
          const lat = row.lat;
          const lon = row.lon;

          const minLat = Math.max(lat - halfLat, GRID_MIN_LAT);
          const maxLat = Math.min(lat + halfLat, GRID_MAX_LAT);
          const minLon = Math.max(lon - halfLon, GRID_MIN_LON);
          const maxLon = Math.min(lon + halfLon, GRID_MAX_LON);

          return {
            id: String(row.cell_id),
            cellId: row.cell_id,
            minLat,
            maxLat,
            minLon,
            maxLon,
            risk: row.risk_score,
          };
        });

        setGridCells(cells);
      } catch (err) {
        console.error("Failed to load risk grid from /risk/latest", err);
        setGridCells([]);
      }
    }

    fetchRisk();
  }, []);

  useEffect(() => {
    async function fetchAll() {
      try {
        const fleetConfigs: { fleet_type: FleetType; stations: StationInput[] }[] =
          [
            {
              fleet_type: "fire",
              stations: fireStations ?? FIRE_STATION_INPUTS,
            },
            {
              fleet_type: "police",
              stations: policeStations ?? POLICE_STATION_INPUTS,
            },
          ];

        const allStations: StationWithFlag[] = [];
        const allTrips: TripWithMeta[] = [];
        const activeStationIds = new Set<string>();

        for (const config of fleetConfigs) {
          const { fleet_type, stations: inputStations } = config;

          const deployRes = await fetch(`${API_BASE}/optimize/deployment`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              fleet_type,
              stations: inputStations,
            }),
          });

          if (!deployRes.ok) {
            console.error(
              `/optimize/deployment failed for ${fleet_type}:`,
              deployRes.status,
              deployRes.statusText
            );
            continue;
          }

          const deployment: DeploymentResponse = await deployRes.json();
          const fleetFromBackend =
            (deployment.fleet_type as FleetType) ?? fleet_type;

          deployment.moves.forEach((move) => {
            activeStationIds.add(move.from_station_id);
            activeStationIds.add(move.to_station_id);
          });

          const stationsWithFleet: StationWithFlag[] = deployment.stations.map(
            (s) => ({
              ...s,
              fleet_type: fleetFromBackend,
              inMove: activeStationIds.has(s.station_id),
            })
          );
          allStations.push(...stationsWithFleet);

          const stationById: Record<string, StationDeployment> = {};
          deployment.stations.forEach((s) => {
            stationById[s.station_id] = s;
          });

          const routeResponses = await Promise.all(
            deployment.moves.map(async (move) => {
              const from = stationById[move.from_station_id];
              const to = stationById[move.to_station_id];
              if (!from || !to) {
                console.warn("Move references unknown station", move);
                return null;
              }

              const routeRes = await fetch(`${API_BASE}/route`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  start_lat: from.lat,
                  start_lon: from.lon,
                  end_lat: to.lat,
                  end_lon: to.lon,
                }),
              });

              if (!routeRes.ok) {
                console.error(
                  `/route failed for move ${move.from_station_id}->${move.to_station_id}`,
                  routeRes.status
                );
                return null;
              }

              const routeJson = await routeRes.json();
              return { routeJson, move, from, to };
            })
          );

          for (let i = 0; i < routeResponses.length; i++) {
            const entry = routeResponses[i];
            if (!entry) continue;
            const { routeJson, move, from, to } = entry;

            const path: TripPoint[] = routeJson.points.map((p: any) => ({
              lat: p.lat,
              lon: p.lon,
              time: p.time,
            }));

            const baseTrip: TripWithMeta = {
              id: `${fleetFromBackend}_${move.from_station_id}_${move.to_station_id}_${i}`,
              fleet_type: fleetFromBackend,
              type: fleetFromBackend === "fire" ? "fire_truck" : "police_car",
              side: "friendly",
              path,
              fromStationId: move.from_station_id,
              toStationId: move.to_station_id,
              fromStationName:
                (from as any).station_name ??
                (from as any).name ??
                move.from_station_id,
              toStationName:
                (to as any).station_name ?? (to as any).name ?? move.to_station_id,
            };

            allTrips.push(baseTrip);
          }
        }

        setStations(allStations);
        if (allTrips.length === 0) {
          setTrips(SAMPLE_TRIPS as TripWithMeta[]);
        } else {
          setTrips(allTrips);
        }
        setCurrentTime(0);
      } catch (err) {
        console.error(
          "Failed to load deployment/routes from backend, using SAMPLE_TRIPS",
          err
        );
        setStations([]);
        setTrips(SAMPLE_TRIPS as TripWithMeta[]);
        setCurrentTime(0);
      }
    }

    fetchAll();
  }, [fireStations, policeStations]);

  const maxTime = useMemo(() => {
    if (!trips || trips.length === 0) return 0;
    return Math.max(...trips.map((t) => t.path[t.path.length - 1]?.time ?? 0));
  }, [trips]);

  useEffect(() => {
    if (!playing || maxTime === 0) return;

    const id = window.setInterval(() => {
      setCurrentTime((prev) => {
        if (!maxTime) return prev;
        const next = prev + playbackSpeed;
        if (next >= maxTime) return 0;
        return next;
      });
    }, 100);

    return () => window.clearInterval(id);
  }, [playing, maxTime, playbackSpeed]);

  const toggleStyle = () => setIsSatellite((prev) => !prev);

  const toggleTilt = () => {
    setIsTilted((prev) => {
      const next = !prev;
      setViewState((v) => ({
        ...v,
        pitch: next ? 45 : 0,
        bearing: next ? 30 : 0,
      }));
      return next;
    });
  };

  const mapStyle = isSatellite
    ? "mapbox://styles/mapbox/satellite-streets-v12"
    : "mapbox://styles/mapbox/streets-v12";

  const selectedTrip: TripWithMeta | null = useMemo(() => {
    if (!trips || !selectedTripId) return null;
    return trips.find((t) => t.id === selectedTripId) ?? null;
  }, [trips, selectedTripId]);

  const selectedStation: StationWithFlag | null = useMemo(() => {
    if (!selectedStationId) return null;
    return (
      stations.find(
        (s) => (s as any).station_id === selectedStationId
      ) ?? null
    );
  }, [stations, selectedStationId]);

  const selectedCell: GridCell | null = useMemo(() => {
    if (selectedCellId === null) return null;
    return gridCells.find((cell) => cell.cellId === selectedCellId) ?? null;
  }, [gridCells, selectedCellId]);

  useEffect(() => {
    if (!onContextChange) return;
    const focusedCellId =
      selectedCellId ??
      latLonToCellId(viewState.latitude, viewState.longitude);

    const selectedStationContext = selectedStation
      ? {
          station_id: (selectedStation as any).station_id,
          name:
            (selectedStation as any).station_name ??
            (selectedStation as any).name,
          fleet_type: selectedStation.fleet_type,
          lat: selectedStation.lat,
          lon: selectedStation.lon,
          in_move: selectedStation.inMove ?? false,
        }
      : null;

    const selectedTripContext = selectedTrip
      ? {
          id: selectedTrip.id,
          fleet_type: selectedTrip.fleet_type,
          from_station_id: selectedTrip.fromStationId,
          to_station_id: selectedTrip.toStationId,
        }
      : null;

    const stationIds = stations
      .map((s) => (s as any).station_id)
      .filter(Boolean);
    const movingStationIds = stations
      .filter((s) => s.inMove)
      .map((s) => (s as any).station_id)
      .filter(Boolean);
    const moves = (trips ?? [])
      .map((t) => ({
        from_station_id: t.fromStationId,
        to_station_id: t.toStationId,
        fleet_type: t.fleet_type,
      }))
      .filter((m) => m.from_station_id && m.to_station_id)
      .slice(0, 20);

    const context: ChatContext = {
      map: {
        center: { lat: viewState.latitude, lon: viewState.longitude },
        zoom: viewState.zoom,
        pitch: viewState.pitch,
        bearing: viewState.bearing,
      },
      focused_cell_id: focusedCellId,
      selected_cell_id: selectedCellId,
      selected_station: selectedStationContext,
      selected_trip: selectedTripContext,
      deployment: {
        station_ids: stationIds,
        moving_station_ids: movingStationIds,
        moves,
      },
    };

    onContextChange(context);
  }, [
    onContextChange,
    viewState,
    selectedCellId,
    selectedStation,
    selectedTrip,
    stations,
    trips,
  ]);

  const startLatLon: [number, number] | null = selectedTrip
    ? [selectedTrip.path[0].lat, selectedTrip.path[0].lon]
    : null;

  const endLatLon: [number, number] | null = selectedTrip
    ? [
        selectedTrip.path[selectedTrip.path.length - 1].lat,
        selectedTrip.path[selectedTrip.path.length - 1].lon,
      ]
    : null;

  const liveLatLon: [number, number] | null = selectedTrip
    ? (() => {
        const [lon, lat] = interpolatePosition(selectedTrip.path, currentTime);
        return [lat, lon];
      })()
    : null;

  const handlePopupMouseDown = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      setIsDraggingPopup(true);
      setDragOffset({
        x: e.clientX - popupPos.x,
        y: e.clientY - popupPos.y,
      });
    },
    [popupPos]
  );

  useEffect(() => {
    if (!isDraggingPopup) return;

    function onMove(e: MouseEvent) {
      setPopupPos({
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y,
      });
    }

    function onUp() {
      setIsDraggingPopup(false);
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);

    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [isDraggingPopup, dragOffset]);

  const tickFractions = [0, 0.25, 0.5, 0.75, 1];

  const moveLayer = (index: number, dir: "up" | "down") => {
    setLayerConfig((prev) => {
      const next = [...prev];
      const newIndex = dir === "up" ? index - 1 : index + 1;
      if (newIndex < 0 || newIndex >= next.length) return prev;
      const item = next[index];
      next.splice(index, 1);
      next.splice(newIndex, 0, item);
      return next;
    });
  };

  const toggleLayerVisibility = (key: LayerKey) => {
    setLayerConfig((prev) =>
      prev.map((l) =>
        l.key === key ? { ...l, visible: !l.visible } : l
      )
    );
  };

  const layers = useMemo(() => {
    if (!trips) return [];

    const heatmapLayer = new PolygonLayer<GridCell>({
      id: "risk-grid",
      data: gridCells,
      pickable: true,
      stroked: true,
      filled: true,
      getPolygon: (d: GridCell) => [
        [d.minLon, d.minLat],
        [d.minLon, d.maxLat],
        [d.maxLon, d.maxLat],
        [d.maxLon, d.minLat],
      ],
      getFillColor: (d: GridCell) => riskToColor(d.risk),
      getLineColor: (d: GridCell) =>
        d.cellId === selectedCellId ? [255, 255, 255, 200] : [0, 0, 0, 0],
      getLineWidth: (d: GridCell) => (d.cellId === selectedCellId ? 2 : 0),
      lineWidthUnits: "pixels",
      opacity: 0.5,
      onClick: (info) => {
        if (!info.object) return;
        const cell = info.object as GridCell;
        setSelectedCellId(cell.cellId);
        setSelectedTripId(null);
        setSelectedStationId(null);
      },
      updateTriggers: {
        getLineColor: [selectedCellId],
        getLineWidth: [selectedCellId],
      },
    });

    const tripsLayer = new TripsLayer<TripWithMeta>({
      id: "trips",
      data: trips,
      getPath: (d: TripWithMeta): Position[] =>
        d.path.map((p) => [p.lon, p.lat] as Position),
      getTimestamps: (d: TripWithMeta) => d.path.map((p) => p.time),
      getColor: (d: TripWithMeta) => fleetPathColor(d.fleet_type),
      widthMinPixels: 5,
      trailLength: 90,
      currentTime,
      rounded: true,
    });

    const vehicleIconsLayer = new IconLayer<TripWithMeta>({
      id: "vehicle-icons",
      data: trips,
      pickable: true,
      billboard: true,
      getPosition: (d: TripWithMeta): Position => {
        const [lon, lat] = interpolatePosition(d.path, currentTime);
        return [lon, lat] as Position;
      },
      getIcon: (d: TripWithMeta) =>
        d.fleet_type === "fire"
          ? {
              url: "/icons/fire-truck.png",
              width: 128,
              height: 128,
              anchorY: 64,
            }
          : {
              url: "/icons/police-car.png",
              width: 128,
              height: 128,
              anchorY: 64,
            },
      sizeUnits: "pixels",
      getSize: 28,
      getColor: () => [255, 255, 255],
      updateTriggers: {
        getPosition: [currentTime],
      },
      parameters: {
        depthTest: false,
      },
      onClick: (info) => {
        if (!info.object) return;
        setSelectedTripId((info.object as TripWithMeta).id);
        setSelectedStationId(null);
        setSelectedCellId(null);
      },
    });

    const stationIconsLayer = new IconLayer<StationWithFlag>({
      id: "station-icons",
      data: stations,
      pickable: true,
      billboard: true,
      getPosition: (s: StationWithFlag): Position => [s.lon, s.lat],
      getIcon: (s: StationWithFlag) =>
        s.fleet_type === "fire"
          ? {
              url: "/icons/fire-station.png",
              width: 128,
              height: 128,
              anchorY: 64,
            }
          : {
              url: "/icons/police-station.png",
              width: 128,
              height: 128,
              anchorY: 64,
            },
      sizeUnits: "pixels",
      getSize: 22,
      getColor: (s: StationWithFlag) => [
        255,
        255,
        255,
        s.inMove ? 255 : 26,
      ],
      parameters: {
        depthTest: false,
      },
      onClick: (info) => {
        if (!info.object) return;
        const station = info.object as StationWithFlag;
        setSelectedStationId((station as any).station_id);
        setSelectedTripId(null);
        setSelectedCellId(null);
      },
    });

    const registry: Record<LayerKey, any[]> = {
      heatmap: [heatmapLayer],
      vehicles: [tripsLayer],
      vehicleIcons: [vehicleIconsLayer],
      stations: [stationIconsLayer],
    };

    const ordered: any[] = [];
    layerConfig.forEach((cfg) => {
      if (!cfg.visible) return;
      const arr = registry[cfg.key];
      if (arr) ordered.push(...arr);
    });

    return ordered;
  }, [trips, gridCells, stations, currentTime, layerConfig, selectedCellId]);

  if (!trips) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          background: "black",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        Loading deployment & routes…
      </div>
    );
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        ...(style || {}),
      }}
    >
      <DeckGL
        controller
        layers={layers}
        viewState={viewState}
        onViewStateChange={({ viewState }) => setViewState(viewState)}
        style={{ width: "100%", height: "100%" }}
        width="100%"
        height="100%"
        onClick={(info) => {
          if (!info.object) {
            setSelectedTripId(null);
            setSelectedStationId(null);
            setSelectedCellId(null);
          }
        }}
      >
        <Map
          mapboxAccessToken={MAPBOX_TOKEN}
          mapStyle={mapStyle}
          attributionControl={false}
          style={{ width: "100%", height: "100%" }}
        />
      </DeckGL>

      <div
        style={{
          position: "absolute",
          top: 24,
          right: 24,
          fontFamily: "system-ui, sans-serif",
          fontSize: 12,
          color: "#e5e7eb",
        }}
      >
        {layerPanelOpen ? (
          <div
            style={{
              padding: "10px 12px",
              borderRadius: 14,
              background: "rgba(0,0,0,0.86)",
              backdropFilter: "blur(18px)",
              boxShadow: "0 16px 32px rgba(0,0,0,0.5)",
              minWidth: 220,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 6,
              }}
            >
              <span style={{ fontWeight: 600, fontSize: 13 }}>Layers</span>
              <button
                onClick={() => setLayerPanelOpen(false)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: "#9ca3af",
                  cursor: "pointer",
                  fontSize: 14,
                }}
              >
                ✕
              </button>
            </div>
            <div
              style={{
                borderTop: "1px solid rgba(148,163,184,0.45)",
                paddingTop: 6,
                display: "flex",
                flexDirection: "column",
                gap: 4,
              }}
            >
              {layerConfig.map((layer, idx) => (
                <div
                  key={layer.key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 8,
                    padding: "4px 6px",
                    borderRadius: 8,
                    background: layer.visible
                      ? "rgba(15,23,42,0.9)"
                      : "transparent",
                  }}
                >
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={layer.visible}
                      onChange={() => toggleLayerVisibility(layer.key)}
                      style={{ cursor: "pointer" }}
                    />
                    <span>{layer.label}</span>
                  </label>
                  <div
                    style={{
                      display: "flex",
                      gap: 4,
                    }}
                  >
                    <button
                      onClick={() => moveLayer(idx, "up")}
                      style={{
                        border: "none",
                        background: "rgba(31,41,55,0.9)",
                        color: "#e5e7eb",
                        cursor: "pointer",
                        borderRadius: 999,
                        padding: "2px 6px",
                        fontSize: 11,
                      }}
                    >
                      ↑
                    </button>
                    <button
                      onClick={() => moveLayer(idx, "down")}
                      style={{
                        border: "none",
                        background: "rgba(31,41,55,0.9)",
                        color: "#e5e7eb",
                        cursor: "pointer",
                        borderRadius: 999,
                        padding: "2px 6px",
                        fontSize: 11,
                      }}
                    >
                      ↓
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <button
            onClick={() => setLayerPanelOpen(true)}
            style={{
              padding: "6px 12px",
              borderRadius: 999,
              border: "1px solid rgba(148,163,184,0.7)",
              background: "rgba(0,0,0,0.8)",
              backdropFilter: "blur(16px)",
              color: "#e5e7eb",
              cursor: "pointer",
              boxShadow: "0 10px 24px rgba(0,0,0,0.45)",
            }}
          >
            Layers
          </button>
        )}
      </div>

      {controlsCollapsed ? (
        <div
          style={{
            position: "absolute",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "8px 14px",
            borderRadius: 999,
            background: "rgba(0,0,0,0.82)",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            gap: 12,
            fontFamily: "system-ui, sans-serif",
            fontSize: 13,
            boxShadow: "0 18px 40px rgba(0,0,0,0.5)",
            backdropFilter: "blur(14px)",
          }}
        >
          <button
            onClick={() => setPlaying((p) => !p)}
            style={{
              cursor: "pointer",
              borderRadius: 999,
              border: "1px solid rgba(255,255,255,0.45)",
              padding: "4px 14px",
              fontSize: 13,
              fontWeight: 500,
              background: playing ? "#e5f0ff" : "rgba(15,23,42,0.9)",
              color: playing ? "#111827" : "#e5e7eb",
              minWidth: 72,
            }}
          >
            {playing ? "Pause" : "Play"}
          </button>
          <span
            style={{
              fontSize: 11,
              opacity: 0.9,
              minWidth: 72,
            }}
          >
            {formatTimeSeconds(currentTime)} / {formatTimeSeconds(maxTime)}
          </span>
          <button
            onClick={() => setControlsCollapsed(false)}
            style={{
              cursor: "pointer",
              borderRadius: 999,
              border: "none",
              background: "rgba(15,23,42,0.9)",
              color: "#e5e7eb",
              padding: "4px 8px",
              fontSize: 14,
            }}
          >
            ▴
          </button>
        </div>
      ) : (
        <div
          style={{
            position: "absolute",
            bottom: 24,
            left: "50%",
            transform: "translateX(-50%)",
            padding: "14px 18px 16px",
            borderRadius: 18,
            background: "rgba(0,0,0,0.82)",
            color: "#fff",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            width: 560,
            minWidth: 560,
            maxWidth: 560,
            fontFamily: "system-ui, sans-serif",
            fontSize: 13,
            boxShadow: "0 18px 40px rgba(0,0,0,0.5)",
            backdropFilter: "blur(14px)",
          }}
        >
          <div
            style={{
              display: "flex",
              gap: 12,
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button
                onClick={() => setPlaying((p) => !p)}
                style={{
                  cursor: "pointer",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.45)",
                  padding: "6px 18px",
                  fontSize: 13,
                  fontWeight: 500,
                  background: playing ? "#e5f0ff" : "rgba(15,23,42,0.9)",
                  color: playing ? "#111827" : "#e5e7eb",
                  minWidth: 84,
                }}
              >
                {playing ? "Pause" : "Play"}
              </button>
              <button
                onClick={toggleStyle}
                style={{
                  cursor: "pointer",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.28)",
                  padding: "6px 16px",
                  fontSize: 13,
                  background: "rgba(15,23,42,0.9)",
                  color: "#f9fafb",
                  minWidth: 110,
                }}
              >
                {isSatellite ? "Streets view" : "Satellite view"}
              </button>
              <button
                onClick={toggleTilt}
                style={{
                  cursor: "pointer",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.28)",
                  padding: "6px 16px",
                  fontSize: 13,
                  background: "rgba(15,23,42,0.9)",
                  color: "#f9fafb",
                  minWidth: 96,
                }}
              >
                {isTilted ? "Flat 2D" : "Tilted 2D"}
              </button>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ fontSize: 11, opacity: 0.8 }}>Speed</span>
              <select
                value={playbackSpeed}
                onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
                style={{
                  background: "rgba(15,23,42,0.95)",
                  color: "#fff",
                  borderRadius: 999,
                  border: "1px solid rgba(255,255,255,0.3)",
                  padding: "4px 10px",
                  fontSize: 12,
                  cursor: "pointer",
                }}
              >
                <option value={0.5}>0.5x</option>
                <option value={1}>1x</option>
                <option value={2}>2x</option>
                <option value={4}>4x</option>
              </select>
              <span
                style={{
                  fontSize: 11,
                  opacity: 0.85,
                  minWidth: 96,
                  textAlign: "right",
                }}
              >
                {formatTimeSeconds(currentTime)} / {formatTimeSeconds(maxTime)}
              </span>
              <button
                onClick={() => setControlsCollapsed(true)}
                style={{
                  cursor: "pointer",
                  borderRadius: 999,
                  border: "none",
                  background: "rgba(15,23,42,0.9)",
                  color: "#e5e7eb",
                  padding: "4px 8px",
                  fontSize: 14,
                  marginLeft: 4,
                }}
              >
                ▾
              </button>
            </div>
          </div>

          <div style={{ marginTop: 4, position: "relative" }}>
            <input
              type="range"
              min={0}
              max={Math.max(maxTime, 1)}
              step={1}
              value={currentTime}
              onChange={(e) => {
                setCurrentTime(Number(e.target.value));
                setPlaying(false);
              }}
              style={{
                width: "100%",
                cursor: "pointer",
                accentColor: "#3b82f6",
                background: "transparent",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: "50%",
                height: 0,
                pointerEvents: "none",
              }}
            >
              {tickFractions.map((f) => (
                <div
                  key={f}
                  style={{
                    position: "absolute",
                    left: `${f * 100}%`,
                    transform: "translateX(-0.5px)",
                    height: 8,
                    borderLeft: "1px solid rgba(148,163,184,0.8)",
                    marginTop: 6,
                  }}
                />
              ))}
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                marginTop: 10,
                fontSize: 11,
                opacity: 0.75,
              }}
            >
              {tickFractions.map((f) => (
                <span key={f}>
                  {formatTimeSeconds((maxTime || 0) * f)}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {(selectedTrip || selectedStation || selectedCell) && (
        <div
          style={{
            position: "absolute",
            left: popupPos.x,
            top: popupPos.y,
            background: "rgba(0,0,0,0.85)",
            color: "#f9fafb",
            padding: "10px 12px 10px",
            borderRadius: 14,
            fontSize: 12,
            boxShadow: "0 14px 30px rgba(0,0,0,0.5)",
            pointerEvents: "auto",
            minWidth: 240,
            maxWidth: 320,
            backdropFilter: "blur(16px)",
            fontFamily: "system-ui, sans-serif",
          }}
        >
          <div
            onMouseDown={handlePopupMouseDown}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              cursor: "grab",
              paddingBottom: 4,
            }}
          >
            <div
              style={{
                fontWeight: 600,
                fontSize: 13,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {selectedTrip
                ? selectedTrip.id
                : selectedStation
                ? (selectedStation as any).station_name ??
                  (selectedStation as any).name ??
                  (selectedStation as any).station_id
                : selectedCell
                ? `Cell ${selectedCell.cellId}`
                : ""}
            </div>
            <button
              onClick={() => {
                setSelectedTripId(null);
                setSelectedStationId(null);
                setSelectedCellId(null);
              }}
              style={{
                border: "none",
                background: "transparent",
                color: "#9ca3af",
                cursor: "pointer",
                fontSize: 13,
                padding: 0,
              }}
            >
              ✕
            </button>
          </div>

          <div
            style={{
              borderTop: "1px solid rgba(148,163,184,0.4)",
              paddingTop: 6,
              display: "grid",
              gridTemplateColumns: "auto 1fr",
              rowGap: 4,
              columnGap: 8,
            }}
          >
            {selectedTrip && (
              <>
                <span style={{ opacity: 0.7 }}>Fleet</span>
                <span>
                  {selectedTrip.fleet_type} · {selectedTrip.type}
                </span>

                {liveLatLon && (
                  <>
                    <span style={{ opacity: 0.7 }}>Position</span>
                    <span>
                      {liveLatLon[0].toFixed(4)}, {liveLatLon[1].toFixed(4)}
                    </span>
                  </>
                )}

                {startLatLon && (
                  <>
                    <span style={{ opacity: 0.7 }}>Start</span>
                    <span>
                      {selectedTrip.fromStationName ??
                        selectedTrip.fromStationId}{" "}
                      · {startLatLon[0].toFixed(4)}, {startLatLon[1].toFixed(4)}
                    </span>
                  </>
                )}

                {endLatLon && (
                  <>
                    <span style={{ opacity: 0.7 }}>Destination</span>
                    <span>
                      {selectedTrip.toStationName ?? selectedTrip.toStationId} ·{" "}
                      {endLatLon[0].toFixed(4)}, {endLatLon[1].toFixed(4)}
                    </span>
                  </>
                )}
              </>
            )}

            {selectedStation && (
              <>
                <span style={{ opacity: 0.7 }}>Fleet</span>
                <span>
                  {selectedStation.fleet_type} station
                </span>

                <span style={{ opacity: 0.7 }}>Position</span>
                <span>
                  {selectedStation.lat.toFixed(4)},{" "}
                  {selectedStation.lon.toFixed(4)}
                </span>

                <span style={{ opacity: 0.7 }}>In move</span>
                <span>{selectedStation.inMove ? "Yes" : "No"}</span>
              </>
            )}

            {selectedCell && (
              <>
                <span style={{ opacity: 0.7 }}>Cell ID</span>
                <span>{selectedCell.cellId}</span>

                <span style={{ opacity: 0.7 }}>Risk</span>
                <span>{selectedCell.risk.toFixed(2)}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
