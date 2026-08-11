"use client";

import { motion } from "framer-motion";
import { useGameStore } from "@/store/useGameStore";
import type { PlayerSetup } from "@/lib/types";

const FIELDS: {
  key: keyof PlayerSetup;
  label: string;
  placeholder: string;
  textarea?: boolean;
}[] = [
  {
    key: "world_choice",
    label: "World",
    placeholder: "Death Note",
  },
  {
    key: "character_name",
    label: "Your name",
    placeholder: "Jay",
  },
  {
    key: "goal",
    label: "Your goal",
    placeholder: "Prove Light is Kira without dying",
    textarea: true,
  },
  {
    key: "personality",
    label: "Personality",
    placeholder: "Paranoid, observant, uses humor to deflect",
    textarea: true,
  },
  {
    key: "background",
    label: "Background",
    placeholder: "Transfer student, ex-detective assistant, father killed by Kira",
    textarea: true,
  },
  {
    key: "starting_position",
    label: "Starting position",
    placeholder: "In class next to Light, L is watching",
    textarea: true,
  },
];

export function PlayerSetupScreen() {
  const setupPlayer = useGameStore((s) => s.setupPlayer);

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const p: PlayerSetup = {
      world_choice: String(data.get("world_choice") || "Death Note").trim(),
      character_name: String(data.get("character_name") || "").trim(),
      goal: String(data.get("goal") || "").trim(),
      personality: String(data.get("personality") || "").trim(),
      background: String(data.get("background") || "").trim(),
      starting_position: String(data.get("starting_position") || "").trim(),
      own_plan: "",
    };
    if (!p.character_name || !p.goal) return;
    setupPlayer(p);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg p-4">
      <motion.form
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={submit}
        className="w-full max-w-lg rounded-2xl border border-edge bg-surface p-8 shadow-2xl"
      >
        <h1 className="text-2xl font-bold tracking-tight text-ink">Enter a living world</h1>
        <p className="mt-1 text-sm text-muted">
          Define who you are and what you want. The world won&apos;t tell you how to win.
        </p>

        <div className="mt-6 space-y-4">
          {FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-xs font-medium uppercase tracking-wide text-muted">
                {f.label}
              </span>
              {f.textarea ? (
                <textarea
                  name={f.key}
                  placeholder={f.placeholder}
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent"
                />
              ) : (
                <input
                  name={f.key}
                  placeholder={f.placeholder}
                  className="mt-1 w-full rounded-lg border border-edge bg-surface-2 px-3 py-2 text-sm text-ink placeholder:text-muted/50 outline-none focus:border-accent"
                />
              )}
            </label>
          ))}
        </div>

        <button
          type="submit"
          className="mt-6 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent/90"
        >
          Enter the world
        </button>
      </motion.form>
    </div>
  );
}
