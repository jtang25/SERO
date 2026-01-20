// pages/home.tsx
import { useState } from "react";
import type { NextPage } from "next";
import dynamic from "next/dynamic";

import StationsEditor from "../components/StationEditor";
import ChatPanel from "../components/ChatPanel";
import { FIRE_STATION_INPUTS, POLICE_STATION_INPUTS } from "../data/stations";
import type { StationInput } from "../types/vehicles";
import type { ChatContext } from "../types/chat";

// Load DeckGL + Map only on client
const VehiclesMap = dynamic(() => import("../components/Vehicles"), {
  ssr: false,
}); 

type PanelKey = "vehicles" | "stations";
type NavKey = PanelKey | "chat";

const HomePage: NextPage = () => {
  const [activePanel, setActivePanel] = useState<PanelKey>("vehicles");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatContext, setChatContext] = useState<ChatContext>({});
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [fireStations, setFireStations] = useState<StationInput[]>(
    FIRE_STATION_INPUTS
  );
  const [policeStations, setPoliceStations] = useState<StationInput[]>(
    POLICE_STATION_INPUTS
  );

  const navItems: { key: NavKey; label: string; short: string }[] = [
    { key: "vehicles", label: "Vehicle simulation", short: "V" },
    { key: "stations", label: "Station editor", short: "S" },
    { key: "chat", label: "Chat", short: "C" },
  ];

  const handleNavClick = (key: NavKey) => {
    if (key === "chat") {
      setChatOpen((prev) => !prev);
      setActivePanel("vehicles");
      return;
    }
    setActivePanel(key);
    setChatOpen(false);
  };

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        width: "100vw",
        background: "#05070b",
        color: "#f5f5f5",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      {/* Sidebar */}
      <div
        style={{
          width: sidebarCollapsed ? 72 : 260,
          transition: "width 0.18s ease",
          borderRight: "1px solid #12141c",
          background: "radial-gradient(circle at top, #131824 0, #05070b 55%)",
          display: "flex",
          flexDirection: "column",
          boxSizing: "border-box",
          padding: sidebarCollapsed ? "12px 8px" : "16px 12px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 18,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 8,
              background:
                "linear-gradient(135deg, rgba(255,96,96,0.9), rgba(72,144,255,0.9))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              fontWeight: 600,
            }}
          >
            A
          </div>
          {!sidebarCollapsed && (
            <div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>Seattle AIP</div>
              <div style={{ fontSize: 11, color: "#8a8fa0" }}>
                Deployment console
              </div>
            </div>
          )}
          <button
            onClick={() => setSidebarCollapsed((c) => !c)}
            style={{
              marginLeft: "auto",
              borderRadius: 999,
              border: "1px solid #33384b",
              background: "rgba(5,7,11,0.8)",
              color: "#9ca0b5",
              width: 26,
              height: 26,
              fontSize: 13,
              cursor: "pointer",
            }}
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {sidebarCollapsed ? "›" : "‹"}
          </button>
        </div>

        <div style={{ fontSize: 11, textTransform: "uppercase", color: "#6f7387", marginBottom: 8 }}>
          {!sidebarCollapsed ? "Views" : ""}
        </div>

        <nav style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {navItems.map((item) => {
            const isActive =
              item.key === "chat" ? chatOpen : activePanel === item.key;

            const buttonStyle: React.CSSProperties = sidebarCollapsed
              ? {
                  borderRadius: 999,
                  border: "none",
                  padding: 8,
                  background: "transparent",
                  color: isActive ? "#e4e7ff" : "#9ca0b5",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 13,
                }
              : {
                  borderRadius: 999,
                  border: "none",
                  textAlign: "left",
                  padding: "8px 12px",
                  background: isActive
                    ? "linear-gradient(90deg, #1e2435, #121829)"
                    : "transparent",
                  color: isActive ? "#e4e7ff" : "#9ca0b5",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  fontSize: 13,
                };

            const iconStyle: React.CSSProperties = {
              width: 32,
              height: 32,
              borderRadius: 999,
              background: isActive
                ? "linear-gradient(135deg, #ff6767, #4b8dff)"
                : "rgba(255,255,255,0.04)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 13,
            };

            return (
              <button
                key={item.key}
                onClick={() => handleNavClick(item.key)}
                style={buttonStyle}
              >
                <span style={iconStyle}>{item.short}</span>
                {!sidebarCollapsed && <span>{item.label}</span>}
              </button>
            );
          })}

        </nav>

        {!sidebarCollapsed && (
          <div
            style={{
              marginTop: "auto",
              fontSize: 11,
              color: "#6f7387",
              paddingTop: 10,
              borderTop: "1px solid #11141f",
            }}
          >
            <div>Scenario: Seattle core</div>
            <div style={{ color: "#9ca0b5", marginTop: 2 }}>
              Risk feed: live /risk/latest
            </div>
          </div>
        )}
      </div>

      {/* Main content area */}
      <div style={{ flex: 1, position: "relative" }}>
        {activePanel === "vehicles" && (
          <>
            <VehiclesMap
              fireStations={fireStations}
              policeStations={policeStations}
              onContextChange={setChatContext}
            />
            {chatOpen && (
              <div
                style={{
                  position: "absolute",
                  top: 24,
                  right: 24,
                  display: "flex",
                  alignItems: "stretch",
                  zIndex: 20,
                }}
              >
                <ChatPanel
                  context={chatContext}
                  onClose={() => setChatOpen(false)}
                />
              </div>
            )}
          </>
        )}

        {activePanel === "stations" && (
          <StationsEditor
            fireStations={fireStations}
            policeStations={policeStations}
            onChangeFire={setFireStations}
            onChangePolice={setPoliceStations}
          />
        )}

      </div>
    </div>
  );
};

export default HomePage;
