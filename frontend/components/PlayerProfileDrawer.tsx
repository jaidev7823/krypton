"use client";

import { useGameStore } from "@/store/useGameStore";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <h3 className="text-[10px] font-bold uppercase tracking-widest text-muted">{title}</h3>
      <div className="text-xs text-ink leading-relaxed">{children}</div>
    </div>
  );
}

function ProficiencyBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    practiced: "bg-emerald-500/20 text-emerald-300",
    learning: "bg-amber-500/20 text-amber-300",
    novice: "bg-surface-2 text-muted",
  };
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[level] || colors.novice}`}>
      {level}
    </span>
  );
}

export function PlayerProfileDrawer({ onClose }: { onClose: () => void }) {
  const profile = useGameStore((s) => s.playerProfile);
  if (!profile) return null;

  return (
    <div className="flex h-full flex-col border-l border-edge bg-surface shadow-2xl">
      <div className="flex items-center justify-between border-b border-edge px-4 py-3">
        <h2 className="text-sm font-bold text-ink">Player Profile</h2>
        <button onClick={onClose} className="text-xs text-muted hover:text-ink">&times;</button>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 p-4 text-xs">
        {profile.status && <Section title="Status">{profile.status}</Section>}
        {profile.cash !== undefined && <Section title="Cash">{profile.cash.toLocaleString()}</Section>}
        {profile.reputation && <Section title="Reputation">{profile.reputation}</Section>}

        {profile.resources && profile.resources.length > 0 && (
          <Section title="Resources">
            <ul className="list-disc pl-4">{profile.resources.map((r, idx) => <li key={idx}>{r}</li>)}</ul>
          </Section>
        )}

        {profile.knowledge && profile.knowledge.length > 0 && (
          <Section title="Knowledge">
            <ul className="list-disc pl-4">{profile.knowledge.map((k, idx) => <li key={idx}>{k}</li>)}</ul>
          </Section>
        )}

        {profile.concepts_used && Object.keys(profile.concepts_used).length > 0 && (
          <Section title="Skills">
            <div className="space-y-1">
              {Object.entries(profile.concepts_used).map(([name, stats]) => (
                <div key={name} className="flex items-center gap-2">
                  <span className="font-medium">{name}</span>
                  <ProficiencyBadge level={stats.proficiency} />
                  <span className="text-muted">
                    used {stats.used}x, good {stats.good}x, missed {stats.missed}x
                  </span>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
