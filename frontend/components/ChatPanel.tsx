import { useEffect, useRef, useState } from "react";
import type { ChatContext } from "../types/chat";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type ChatPanelProps = {
  context?: ChatContext;
  apiBase?: string;
  onClose?: () => void;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function ChatPanel({
  context,
  apiBase,
  onClose,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isStreaming]);

  const buildHistory = () =>
    messages.map((m) => ({ role: m.role, content: m.content }));

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;

    setError(null);

    const userMessage: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
    };

    const history = buildHistory();
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${apiBase ?? API_BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          history,
          view_state: context ?? {},
        }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Chat stream failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const lines = part.split("\n");
          for (const rawLine of lines) {
            const line = rawLine.replace(/\r/g, "");
            if (!line.startsWith("data:")) continue;
            let chunk = line.slice(5);
            if (chunk === "[DONE]" || chunk === " [DONE]") {
              buffer = "";
              break;
            }
            if (!chunk) continue;
            assistantText += chunk;
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId ? { ...msg, content: assistantText } : msg
              )
            );
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Streaming failed.");
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleReset = () => {
    setMessages([]);
    setError(null);
  };

  return (
    <div
      style={{
        width: "min(360px, 90vw)",
        height: "min(520px, calc(100vh - 180px))",
        minHeight: 320,
        padding: 18,
        boxSizing: "border-box",
        background: "linear-gradient(180deg, #0b0f18 0%, #05070b 100%)",
        color: "#f5f5f5",
        display: "flex",
        flexDirection: "column",
        borderRadius: 20,
        border: "1px solid #151a27",
        boxShadow: "0 18px 40px rgba(0,0,0,0.6)",
        backdropFilter: "blur(12px)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 16, fontWeight: 600 }}>SERO Copilot</div>
          <div style={{ fontSize: 11, color: "#8c92a6", marginTop: 2 }}>
            Grounded in incident records + live context
          </div>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button
            onClick={handleReset}
            style={{
              borderRadius: 999,
              border: "1px solid #2a3145",
              background: "rgba(5,7,11,0.7)",
              color: "#9ca0b5",
              padding: "6px 10px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            Reset
          </button>
          {onClose && (
            <button
              onClick={onClose}
              style={{
                borderRadius: 999,
                border: "1px solid #2a3145",
                background: "rgba(5,7,11,0.7)",
                color: "#9ca0b5",
                width: 28,
                height: 28,
                cursor: "pointer",
                fontSize: 13,
              }}
              aria-label="Close chat"
            >
              x
            </button>
          )}
        </div>
      </div>

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          borderRadius: 14,
          border: "1px solid #1a2030",
          background: "rgba(10,12,18,0.92)",
          padding: 12,
          fontSize: 13,
          color: "#cbd0e0",
          overflowY: "auto",
          overflowX: "hidden",
          display: "flex",
          flexDirection: "column",
          gap: 10,
          minHeight: 0,
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: "#7c8397", fontSize: 12 }}>
            Ask about incidents, hotspots, or why a cell is risky.
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
              background:
                msg.role === "user"
                  ? "linear-gradient(135deg, #2e4366, #1e2a44)"
                  : "rgba(19,26,40,0.9)",
              color: "#e5e7eb",
              padding: "8px 10px",
              borderRadius: 12,
              maxWidth: "85%",
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
              overflowWrap: "anywhere",
              lineHeight: 1.4,
            }}
          >
            {msg.content || (msg.role === "assistant" && isStreaming ? "..." : "")}
          </div>
        ))}
        {error && (
          <div style={{ color: "#ffb4b4", fontSize: 12 }}>{error}</div>
        )}
      </div>

      <div
        style={{
          marginTop: 12,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Ask about incidents, hotspots, or deployments..."
          rows={2}
          style={{
            width: "100%",
            borderRadius: 14,
            border: "1px solid #262c3f",
            background: "#05070b",
            color: "#e5e7eb",
            padding: "10px 12px",
            fontSize: 13,
            resize: "none",
          }}
        />
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            style={{
              borderRadius: 999,
              border: "none",
              padding: "8px 16px",
              background: isStreaming ? "#33384b" : "#3b82f6",
              color: "#f5f5f5",
              cursor: isStreaming ? "not-allowed" : "pointer",
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {isStreaming ? "Sending..." : "Send"}
          </button>
          <button
            onClick={handleStop}
            disabled={!isStreaming}
            style={{
              borderRadius: 999,
              border: "1px solid #33384b",
              padding: "8px 14px",
              background: "rgba(5,7,11,0.8)",
              color: "#9ca0b5",
              cursor: isStreaming ? "pointer" : "not-allowed",
              fontSize: 12,
            }}
          >
            Stop
          </button>
          <div style={{ fontSize: 11, color: "#7b8197", marginLeft: "auto" }}>
            Shift+Enter for newline
          </div>
        </div>
      </div>
    </div>
  );
}
