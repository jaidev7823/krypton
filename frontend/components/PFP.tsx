"use client";

const PALETTE = [
  "#e11d48",
  "#8b5cf6",
  "#0ea5e9",
  "#22c55e",
  "#f59e0b",
  "#ec4899",
];

export function PFP({
  name,
  id,
  size = 36,
}: {
  name: string;
  id: string;
  size?: number;
}) {
  const initials = (name || id || "?")
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  let hash = 0;
  for (const c of id) hash = (hash * 31 + c.charCodeAt(0)) >>> 0;
  const color = PALETTE[hash % PALETTE.length];

  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full font-bold text-white"
      style={{ width: size, height: size, background: color, fontSize: size * 0.38 }}
    >
      {initials}
    </div>
  );
}
