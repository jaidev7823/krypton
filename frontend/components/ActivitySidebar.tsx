"use client";

import { useGameStore } from "@/store/useGameStore";

export function ActivitySidebar() {
  const notices = useGameStore((s) => s.notices);
  const events = useGameStore((s) => s.events);

  return (
    <aside className="hidden w-72 shrink-0 flex-col overflow-y-auto border-l border-edge bg-surface lg:flex">
      <div className="flex-1 px-4 py-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          Coach feedback
        </h2>
        {notices.length === 0 ? (
          <p className="mt-2 text-xs text-muted/60">No technique feedback yet.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {notices.map((n) => (
              <li
                key={n.id}
                className={`rounded-lg border p-2.5 ${
                  n.ok
                    ? "border-trust/40 bg-trust/10"
                    : "border-suspicion/40 bg-suspicion/10"
                }`}
              >
                <p className="flex items-center gap-1.5 text-[11px] font-semibold text-ink">
                  <span>{n.ok ? "✓" : "✗"}</span>
                  <span className="uppercase tracking-wide">{n.concepts}</span>
                </p>
                <p className="mt-1 line-clamp-2 text-[11px] italic text-muted">
                  “{n.player}”
                </p>
                <p className="mt-1 text-xs text-ink/80">{n.text}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border-t border-edge px-4 py-4">
        <h2 className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          World events
        </h2>
        {events.length === 0 ? (
          <p className="mt-2 text-xs text-muted/60">Nothing has happened yet.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {[...events].reverse().map((e, i) => (
              <li key={`${i}-${e}`} className="flex gap-2 text-xs text-muted">
                <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-accent" />
                <span>{e}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
