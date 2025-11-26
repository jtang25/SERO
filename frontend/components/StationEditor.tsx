// components/StationsEditor.tsx
import type { StationInput } from "../types/vehicles";

type StationsEditorProps = {
  fireStations: StationInput[];
  policeStations: StationInput[];
  onChangeFire: (stations: StationInput[]) => void;
  onChangePolice: (stations: StationInput[]) => void;
};

type StationTableProps = {
  title: string;
  stations: StationInput[];
  onChange: (stations: StationInput[]) => void;
  accent: string;
  badgeLabel: string;
};

function StationTable({
  title,
  stations,
  onChange,
  accent,
  badgeLabel,
}: StationTableProps) {
  const updateField = (
    index: number,
    field: keyof StationInput,
    value: string
  ) => {
    const next = [...stations];
    const current = next[index];

    if (!current) return;

    if (field === "lat" || field === "lon" || field === "vehicles_current") {
      (current as any)[field] = Number(value);
    } else {
      (current as any)[field] = value;
    }

    onChange(next);
  };

  const addRow = () => {
    onChange([
      ...stations,
      {
        station_id: "",
        lat: 47.6,
        lon: -122.33,
        vehicles_current: 1,
      },
    ]);
  };

  const removeRow = (index: number) => {
    const next = stations.filter((_, i) => i !== index);
    onChange(next);
  };

  return (
    <div
      style={{
        flex: "1 1 0",
        minWidth: 420,
        maxWidth: "100%",
        borderRadius: 14,
        border: "1px solid #1b1f2a",
        borderTop: `3px solid ${accent}`,
        padding: 18,
        background:
          "radial-gradient(circle at top left, rgba(255,255,255,0.02), #05070b)",
        boxShadow: "0 14px 30px rgba(0,0,0,0.45)",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        maxHeight: "100%",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
          gap: 12,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span
            style={{
              fontSize: 11,
              letterSpacing: 0.12,
              textTransform: "uppercase",
              color: "#7c8296",
            }}
          >
            {badgeLabel}
          </span>
          <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>
        </div>
        <button
          onClick={addRow}
          style={{
            cursor: "pointer",
            padding: "6px 12px",
            borderRadius: 999,
            border: "none",
            background: accent,
            color: "#fff",
            fontSize: 12,
            fontWeight: 500,
            whiteSpace: "nowrap",
          }}
        >
          + Add station
        </button>
      </div>

      <div
        style={{
          borderRadius: 10,
          border: "1px solid #161822",
          background: "#05070b",
          overflow: "hidden",
          flex: 1,
          minHeight: 0,
        }}
      >
        <div
          className="stations-scroll"
          style={{
            maxHeight: "100%",
            height: "100%",
            overflowY: "auto",
            overflowX: "hidden",
          }}
        >
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: 12,
              tableLayout: "fixed",
            }}
          >
            <thead>
              <tr>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px 10px",
                    fontWeight: 500,
                    color: "#a5aec4",
                    background: "#0a0d16",
                  }}
                >
                  ID
                </th>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px 10px",
                    fontWeight: 500,
                    color: "#a5aec4",
                    background: "#0a0d16",
                  }}
                >
                  Lat
                </th>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px 10px",
                    fontWeight: 500,
                    color: "#a5aec4",
                    background: "#0a0d16",
                  }}
                >
                  Lon
                </th>
                <th
                  style={{
                    textAlign: "left",
                    padding: "8px 10px",
                    fontWeight: 500,
                    color: "#a5aec4",
                    background: "#0a0d16",
                  }}
                >
                  Vehicles
                </th>
                <th
                  style={{
                    padding: "8px 10px",
                    background: "#0a0d16",
                  }}
                />
              </tr>
            </thead>
            <tbody>
              {stations.map((s, idx) => (
                <tr
                  key={s.station_id || idx}
                  style={{
                    borderTop: "1px solid #11141d",
                  }}
                >
                  <td style={{ padding: "6px 8px" }}>
                    <input
                      value={s.station_id}
                      onChange={(e) =>
                        updateField(idx, "station_id", e.target.value)
                      }
                      style={{
                        width: "100%",
                        background: "#05070b",
                        borderRadius: 6,
                        border: "1px solid #292d3a",
                        color: "#fff",
                        padding: "4px 6px",
                        outline: "none",
                        fontSize: 12,
                      }}
                    />
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <input
                      type="number"
                      step="0.000001"
                      value={s.lat}
                      onChange={(e) => updateField(idx, "lat", e.target.value)}
                      style={{
                        width: "100%",
                        background: "#05070b",
                        borderRadius: 6,
                        border: "1px solid #292d3a",
                        color: "#fff",
                        padding: "4px 6px",
                        outline: "none",
                        fontSize: 12,
                      }}
                    />
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <input
                      type="number"
                      step="0.000001"
                      value={s.lon}
                      onChange={(e) => updateField(idx, "lon", e.target.value)}
                      style={{
                        width: "100%",
                        background: "#05070b",
                        borderRadius: 6,
                        border: "1px solid #292d3a",
                        color: "#fff",
                        padding: "4px 6px",
                        outline: "none",
                        fontSize: 12,
                      }}
                    />
                  </td>
                  <td style={{ padding: "6px 8px" }}>
                    <input
                      type="number"
                      min={0}
                      value={s.vehicles_current}
                      onChange={(e) =>
                        updateField(idx, "vehicles_current", e.target.value)
                      }
                      style={{
                        width: "100%",
                        background: "#05070b",
                        borderRadius: 6,
                        border: "1px solid #292d3a",
                        color: "#fff",
                        padding: "4px 6px",
                        outline: "none",
                        fontSize: 12,
                      }}
                    />
                  </td>
                  <td style={{ padding: "6px 8px", textAlign: "center" }}>
                    <button
                      onClick={() => removeRow(idx)}
                      style={{
                        cursor: "pointer",
                        borderRadius: 6,
                        border: "1px solid #303444",
                        background: "transparent",
                        color: "#888ea5",
                        padding: "4px 8px",
                        fontSize: 11,
                      }}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}

              {stations.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    style={{
                      padding: 10,
                      textAlign: "center",
                      color: "#777",
                    }}
                  >
                    No stations yet – add one to get started.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default function StationsEditor({
  fireStations,
  policeStations,
  onChangeFire,
  onChangePolice,
}: StationsEditorProps) {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        padding: 24,
        boxSizing: "border-box",
        color: "#f5f5f5",
        backgroundColor: "#05070b",
        backgroundImage:
          "radial-gradient(circle at top left, rgba(255,255,255,0.045), transparent 55%), repeating-linear-gradient(to bottom, rgba(255,255,255,0.015), rgba(255,255,255,0.015) 1px, transparent 1px, transparent 26px)",
        backgroundBlendMode: "screen",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <h1 style={{ marginTop: 0, marginBottom: 4, fontSize: 20 }}>
        Station Deployment Editor
      </h1>
      <p style={{ marginTop: 0, marginBottom: 20, fontSize: 13, color: "#999" }}>
        Edit fire and police station locations and vehicle counts. Changes are
        used the next time deployments are optimized.
      </p>

      <div
        style={{
          flex: 1,
          display: "flex",
          gap: 24,
          alignItems: "stretch",
          flexWrap: "nowrap",
          minHeight: 0,
          paddingBottom: 12,
        }}
      >
        <StationTable
          title="Fire stations"
          stations={fireStations}
          onChange={onChangeFire}
          accent="#ff6a5a"
          badgeLabel="Fire response"
        />
        <StationTable
          title="Police stations"
          stations={policeStations}
          onChange={onChangePolice}
          accent="#4b8dff"
          badgeLabel="Police response"
        />
      </div>

      <style jsx global>{`
        .stations-scroll {
          scrollbar-width: thin;
          scrollbar-color: rgba(255, 255, 255, 0.16) transparent;
        }
        .stations-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .stations-scroll::-webkit-scrollbar-track {
          background: transparent;
        }
        .stations-scroll::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.14);
          border-radius: 999px;
        }
        .stations-scroll:hover::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.22);
        }
      `}</style>
    </div>
  );
}
