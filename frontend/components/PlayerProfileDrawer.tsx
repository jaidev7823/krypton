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
        {profile.affiliation && <Section title="Affiliation">{profile.affiliation}</Section>}
        {profile.cash !== undefined && <Section title="Cash">{profile.cash}</Section>}
        {profile.public_perception && <Section title="Public Perception">{profile.public_perception}</Section>}

        {profile.items && profile.items.length > 0 && (
          <Section title="Items">
            <ul className="list-disc pl-4">{profile.items.map((i, idx) => <li key={idx}>{i}</li>)}</ul>
          </Section>
        )}

        {profile.documents && profile.documents.length > 0 && (
          <Section title="Documents">
            <ul className="list-disc pl-4">{profile.documents.map((d, idx) => <li key={idx}>{d}</li>)}</ul>
          </Section>
        )}

        {profile.knowledge && profile.knowledge.length > 0 && (
          <Section title="Knowledge">
            <ul className="list-disc pl-4">{profile.knowledge.map((k, idx) => <li key={idx}>{k}</li>)}</ul>
          </Section>
        )}

        {profile.can_go && profile.can_go.length > 0 && (
          <Section title="Access: Locations">
            <ul className="list-disc pl-4">{profile.can_go.map((g, idx) => <li key={idx}>{g}</li>)}</ul>
          </Section>
        )}

        {profile.can_meet && profile.can_meet.length > 0 && (
          <Section title="Access: People">
            <ul className="list-disc pl-4">{profile.can_meet.map((m, idx) => <li key={idx}>{m}</li>)}</ul>
          </Section>
        )}

        {profile.cannot_go && profile.cannot_go.length > 0 && (
          <Section title="Denied: Locations">
            <ul className="list-disc pl-4 text-muted">{profile.cannot_go.map((g, idx) => <li key={idx}>{g}</li>)}</ul>
          </Section>
        )}

        {profile.cannot_meet && profile.cannot_meet.length > 0 && (
          <Section title="Denied: People">
            <ul className="list-disc pl-4 text-muted">{profile.cannot_meet.map((m, idx) => <li key={idx}>{m}</li>)}</ul>
          </Section>
        )}

        {profile.concepts_used && Object.keys(profile.concepts_used).length > 0 && (
          <Section title="Skills Used">
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

        {profile.missed_opportunities && profile.missed_opportunities.length > 0 && (
          <Section title="Missed Opportunities">
            <ul className="list-disc pl-4 text-amber-300">
              {profile.missed_opportunities.map((m, idx) => (
                <li key={idx}><span className="font-medium">{m.concept}</span> — {m.context}</li>
              ))}
            </ul>
          </Section>
        )}

        {profile.growth_markers && profile.growth_markers.length > 0 && (
          <Section title="Growth">
            <ul className="list-disc pl-4 text-emerald-300">{profile.growth_markers.map((g, idx) => <li key={idx}>{g}</li>)}</ul>
          </Section>
        )}

        {profile.debts && profile.debts.length > 0 && (
          <Section title="Debts">
            <ul className="list-disc pl-4">{profile.debts.map((d, idx) => <li key={idx}>{d}</li>)}</ul>
          </Section>
        )}

        {profile.obligations && profile.obligations.length > 0 && (
          <Section title="Obligations">
            <ul className="list-disc pl-4">{profile.obligations.map((o, idx) => <li key={idx}>{o}</li>)}</ul>
          </Section>
        )}

        {profile.exposure && profile.exposure.length > 0 && (
          <Section title="Exposure">
            <ul className="list-disc pl-4 text-amber-300">{profile.exposure.map((e, idx) => <li key={idx}>{e}</li>)}</ul>
          </Section>
        )}

        {profile.connections && profile.connections.length > 0 && (
          <Section title="Connections">
            <ul className="list-disc pl-4">{profile.connections.map((c, idx) => <li key={idx}>{c}</li>)}</ul>
          </Section>
        )}

        {profile.faction_views && Object.keys(profile.faction_views).length > 0 && (
          <Section title="Faction Views">
            <div className="space-y-1">
              {Object.entries(profile.faction_views).map(([faction, view]) => (
                <div key={faction}><span className="font-medium">{faction}:</span> <span className="text-muted">{view}</span></div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}
