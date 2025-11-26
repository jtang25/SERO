// components/ChatPanel.tsx

export default function ChatPanel() {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        padding: 24,
        boxSizing: "border-box",
        background: "#05070b",
        color: "#f5f5f5",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <h1 style={{ marginTop: 0, marginBottom: 8, fontSize: 20 }}>
        Chat (coming soon)
      </h1>
      <p style={{ marginTop: 0, marginBottom: 16, fontSize: 13, color: "#999" }}>
        This will host an operations copilot / chat interface. For now, it&apos;s
        just a skeleton.
      </p>

      <div
        style={{
          flex: 1,
          borderRadius: 12,
          border: "1px solid #222",
          background: "rgba(10,12,18,0.9)",
          padding: 12,
          fontSize: 13,
          color: "#777",
        }}
      >
        Conversation timeline placeholder
      </div>

      <div
        style={{
          marginTop: 12,
          display: "flex",
          gap: 8,
          opacity: 0.5,
        }}
      >
        <input
          disabled
          placeholder="Type a message… (not wired yet)"
          style={{
            flex: 1,
            borderRadius: 999,
            border: "1px solid #333",
            background: "#05070b",
            color: "#999",
            padding: "8px 12px",
          }}
        />
        <button
          disabled
          style={{
            borderRadius: 999,
            border: "none",
            padding: "8px 14px",
            background: "#333",
            color: "#999",
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
