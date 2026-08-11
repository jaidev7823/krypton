"use client";

export function MemoryList({ memory }: { memory: string[] }) {
  if (!memory.length) {
    return (
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted/60">Memory</p>
        <p className="mt-1 text-xs italic text-muted/50">Nothing remembered about you yet.</p>
      </div>
    );
  }
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-muted/60">Memory</p>
      <ul className="mt-2 space-y-1.5">
        {memory.map((m, i) => (
          <li
            key={i}
            className="rounded-lg border border-edge bg-surface-2 px-2.5 py-1.5 text-xs text-muted"
          >
            {m}
          </li>
        ))}
      </ul>
    </div>
  );
}
