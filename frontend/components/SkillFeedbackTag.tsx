"use client";

import type { SkillFeedback } from "@/lib/types";

export function SkillFeedbackTag({ feedback }: { feedback: SkillFeedback }) {
  const ok = feedback.did_use_concept && feedback.did_pass_this_turn;
  const concepts = (feedback.concepts_used || []).join(" + ");

  return (
    <div
      className={`inline-flex max-w-full items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
        ok
          ? "border-trust/40 bg-trust/10 text-trust"
          : "border-suspicion/40 bg-suspicion/10 text-suspicion"
      }`}
      title={feedback.how_properly_used}
    >
      {ok ? "✓" : "✗"}
      <span>{concepts || "NO SKILL"}</span>
      <span className="font-normal opacity-80">·</span>
      <span className="truncate font-normal">{feedback.feedback_for_player}</span>
    </div>
  );
}
