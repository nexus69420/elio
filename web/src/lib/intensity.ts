export type Intensity = "quick" | "assist" | "work" | "deep";

export const INTENSITY_OPTIONS: { id: Intensity; label: string; hint: string }[] = [
  { id: "quick", label: "Quick", hint: "Fast answer, light gates" },
  { id: "assist", label: "Assist", hint: "Tools + ask before writes" },
  { id: "work", label: "Work", hint: "Multi-agent job with approvals" },
  { id: "deep", label: "Deep", hint: "Thorough plan, always HITL" },
];

/** Map composer controls → TaskCreate fields. */
export function resolveTaskOptions(
  intensity: Intensity,
  askBeforeActing: boolean,
  packId: string
): { force_hitl: boolean; preset_id?: string } {
  let force_hitl = askBeforeActing;
  if (intensity === "quick" && !askBeforeActing) force_hitl = false;
  if (intensity === "deep") force_hitl = true;
  if (intensity === "work" && askBeforeActing) force_hitl = true;

  const out: { force_hitl: boolean; preset_id?: string } = { force_hitl };
  if (packId) out.preset_id = packId;
  return out;
}
