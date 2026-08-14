"use client";

const LABEL: Record<string, string> = {
  trust: "Trust",
  familiarity: "Familiarity",
  respect: "Respect",
  suspicion: "Suspicion",
  rapport: "Rapport",
  disclosure_level: "Disclosure",
  stress: "Stress",
};

const GOOD_POSITIVE = new Set(["trust", "familiarity", "respect", "rapport", "disclosure_level"]);

export function StatDeltaChips({ deltas }: { deltas?: Record<string, number> }) {
  if (!deltas) return null;
  const entries = Object.entries(deltas).filter(([, d]) => d !== 0);
  if (entries.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {entries.map(([stat, delta]) => {
        const positive = delta > 0;
        const good = GOOD_POSITIVE.has(stat) ? positive : !positive;
        return (
          <span
            key={stat}
            className={`inline-flex items-center gap-0.5 rounded-full border px-1.5 py-px text-[10px] font-semibold ${
              good
                ? "border-trust/40 bg-trust/10 text-trust"
                : "border-suspicion/40 bg-suspicion/10 text-suspicion"
            }`}
          >
            {positive ? "+" : ""}
            {delta} {LABEL[stat] ?? stat}
          </span>
        );
      })}
    </div>
  );
}
