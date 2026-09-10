import { useEffect, useRef } from "react";

export function mergeOpts(presets: string[] = [], live?: string[]) {
  return Array.from(new Set([...(presets || []), ...(live || []).filter(Boolean)]));
}

export function ModelSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const opts = value && !options.includes(value) ? [value, ...options] : options;
  return (
    <div className="field">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {opts.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <input
        className="model-custom"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Or type a custom model id"
      />
    </div>
  );
}

export function PromptInput({
  value,
  onChange,
  disabled,
  minRows = 4,
  maxHeight = 280,
  placeholder,
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  minRows?: number;
  maxHeight?: number;
  placeholder?: string;
  onSubmit?: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const next = Math.min(Math.max(el.scrollHeight, minRows * 24), maxHeight);
    el.style.height = `${next}px`;
  }, [value, minRows, maxHeight]);

  return (
    <textarea
      ref={ref}
      className="prompt-input"
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      rows={minRows}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => {
        if (onSubmit && e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          onSubmit();
        }
      }}
    />
  );
}

export function HealthLine({ label, on }: { label: string; on: boolean }) {
  return (
    <div className="health-row">
      <span>{label}</span>
      <span className={`dot ${on ? "on" : "off"}`} title={on ? "ok" : "down"} />
    </div>
  );
}
