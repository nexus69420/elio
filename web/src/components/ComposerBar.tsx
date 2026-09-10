import { useEffect, useRef, useState } from "react";
import { ArrowUp, Check, ChevronDown, Infinity as InfinityIcon, Loader2, Plus } from "lucide-react";
import { INTENSITY_OPTIONS, Intensity } from "../lib/intensity";
import { AgentPreset } from "../api";

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onClose: () => void) {
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ref, onClose]);
}

export function ComposerBar({
  value,
  onChange,
  onSend,
  busy,
  intensity,
  onIntensity,
  packId,
  onPack,
  askBeforeActing,
  onAskBeforeActing,
  presets,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  busy?: boolean;
  intensity: Intensity;
  onIntensity: (v: Intensity) => void;
  packId: string;
  onPack: (v: string) => void;
  askBeforeActing: boolean;
  onAskBeforeActing: (v: boolean) => void;
  presets: AgentPreset[];
}) {
  const [openMode, setOpenMode] = useState(false);
  const [openAgent, setOpenAgent] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useClickOutside(wrapRef, () => {
    setOpenMode(false);
    setOpenAgent(false);
  });

  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 24), 140)}px`;
  }, [value]);

  const modeLabel =
    intensity === "assist" ? "Auto" : INTENSITY_OPTIONS.find((o) => o.id === intensity)?.label || "Auto";
  const packName = presets.find((p) => p.id === packId)?.name;

  return (
    <div className="composer" ref={wrapRef}>
      <div className="composer-card">
        {packName && (
          <div className="composer-context">
            <span className="composer-context-label">{packName}</span>
          </div>
        )}

        <textarea
          ref={taRef}
          className="composer-input"
          value={value}
          disabled={busy}
          placeholder="Do anything…"
          rows={1}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
        />

        <div className="composer-toolbar">
          <div className="composer-toolbar-left">
            <button
              type="button"
              className="composer-plus"
              onClick={() => {
                setOpenAgent((v) => !v);
                setOpenMode(false);
              }}
              title="Agent pack"
            >
              <Plus size={16} />
            </button>

            {openAgent && (
              <div className="menu left toolbar-menu">
                <button type="button" className={!packId ? "on" : ""} onClick={() => { onPack(""); setOpenAgent(false); }}>
                  Default team {!packId && <Check size={14} />}
                </button>
                {presets.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    className={packId === p.id ? "on" : ""}
                    onClick={() => { onPack(p.id); setOpenAgent(false); }}
                  >
                    <InfinityIcon size={14} /> {p.name} {packId === p.id && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}

            <label className={`composer-approve ${askBeforeActing ? "on" : ""}`}>
              <input
                type="checkbox"
                checked={askBeforeActing}
                onChange={(e) => onAskBeforeActing(e.target.checked)}
              />
              <span>Ask for approval</span>
            </label>
          </div>

          <div className="composer-toolbar-right">
            <button
              type="button"
              className="composer-auto"
              onClick={() => {
                setOpenMode((v) => !v);
                setOpenAgent(false);
              }}
            >
              {modeLabel} <ChevronDown size={14} />
            </button>

            {openMode && (
              <div className="menu right toolbar-menu">
                {INTENSITY_OPTIONS.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    className={intensity === o.id ? "on" : ""}
                    onClick={() => {
                      onIntensity(o.id);
                      if (o.id === "quick") onAskBeforeActing(false);
                      if (o.id === "deep" || o.id === "work") onAskBeforeActing(true);
                      setOpenMode(false);
                    }}
                  >
                    <span>
                      <strong>{o.label}</strong>
                      <em>{o.hint}</em>
                    </span>
                    {intensity === o.id && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}

            <button
              type="button"
              className="composer-send"
              disabled={busy || !value.trim()}
              onClick={onSend}
              title="Send"
            >
              {busy ? <Loader2 size={14} className="spin" /> : <ArrowUp size={15} strokeWidth={2.5} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
