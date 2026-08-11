PROJECT: Living World Negotiation Game
One-Liner (Updated)

Build a 3-request JSON engine where the player creates a character with a goal, personality and starting position and must devise their own plan to achieve it inside any fictional world, while every canon character in that world acts as an autonomous, self-motivated player with living stats, evaluated by a Skill Engine (Never Split the Difference) and rendered in a living chat UI with Chatterbox cloned voices.
What We Are Building

Not a visual novel. Not a chatbot.

A negotiation simulator where:

    Player is dropped into a fictional world (Starting with Death Note) with ZERO scripted quests. Player defines: name, goal, personality, background, starting position. Player must INVENT their own plan. Game does NOT tell them how to win.

    Every canon character is an autonomous player - They have:
        Own knowledge (what they know / don't know / suspect)
        Own motivation and goal (e.g., L wants to eliminate Jay as suspect, Light wants to recruit Jay)
        Own planning framework (how they scheme)
        Living stats (trust, suspicion towards player) that change every turn
        Memory of player (what they remember about you)
        Private inner thought (Suzerain-style blurred box)

    Core Mechanic = Never Split the Difference
        Player must use real FBI negotiation tactics: Mirroring, Labeling, Accusation Audit, Calibrated Questions
        Listener LLM evaluates if player used tactic correctly considering background
        If correct, autonomous characters react positively, lower suspicion, reveal more info
        If wrong, they punish

    No scripted dialogue - All dialogue generated live by LLM respecting:
        Character's vocab, speech_pattern, never_says
        Character's current plan and objective
        Player's skill usage from previous turn

How It Should Ideally Look & Feel

Reference: Suzerain + Disco Elysium + Death Note anime

    Chat UI: Not boring chat bubbles. Living characters with PFP, name, dialogue that feels like anime scene. Player messages on right, characters on left.
    Narration: Italic grey system text between messages explaining environment - "Classroom noisy after Kanto broadcast..."
    Inspector Drawer: Click L's PFP -> Right drawer slides showing:
        Stat bars: Trust 15% [-10], Suspicion 55% [+15] with animated delta
        Inner Thought: Blurred "He used audit, 60% chance honest..." click to reveal
        Memory List: "Said father killed by Kira", "Used accusation audit in M3"
        Challenge: "L expects LABELING next"
    Coach Button: Top bar -> Explains current required concept with example FROM current chat history
    Audio: Every character line auto-plays in cloned voice (Chatterbox). Player doesn't have to read if they don't want to - just listen and play. Sample audio folder provides voice identity.
    Mission System: Not quest log. Narrator decides if mission won/lost based on stat changes + skill usage. Missions chain logically: M3 Gain L's attention -> M4 Get L's contact -> M5 Access data. Why important is always shown.

Ideal Flow:

    Player types: "You probably think I'm just making up my father story..."
    Skill feedback tag pops instantly: "✓ ACCUSATION_AUDIT Perfect"
    L's stat animates: Trust +20 green
    L replies with voice: "It seems like you're worried no one believes your father's innocence" + audio plays
    Inspector updates: New memory, new inner thought
    Challenge hint updates: "L expects LABELING"

Vibe: Tense, paranoid, you are actually negotiating for your life. Every word matters.
Tech Decomposition (Locked)
Piece 1: Player Setup Module

Input: UI fields
Output: player JSON
Piece 2: World Concept JSON

Input: world_choice
Output: death_note_bible.json (already exists, LOAD only)
Piece 3: Skill Engine

Input: skill_book_choice
Output: never_split_bible.json (already exists)
Piece 4: Prompt Builder + 3 LLM Calls

    R1 Listener/Teacher: Input: skill_bible + player bg + mission convo + new input -> Output: did_use_concept, concepts_used, feedback
    R2 Character Brain (parallel for each char in scene): Input: char bible + char plan + mission + R1 output -> Output: inner_thought, dialogue, stat_changes (delta+reason), challenge_for_player, plan_status
    R3 Narrator/Mission Manager: Input: world lore + player + mission chain + R1 + R2 outputs -> Output: narration, where, why_here, mission_status (won/lost/next), characters_entered/left

Piece 5: Merge

Merge R1+R2+R3 -> Final Game Turn JSON that frontend consumes
Piece 6A: UI Renderer

16 components, core 5: GamePage, ChatContainer, CharacterMessage, InputBar, CharacterInspectorDrawer
Piece 6B: Audio Renderer

Input: character_id + dialogue -> Chatterbox clone with /audio_samples/{id}.wav -> Output: /generated_audio/{turn}_{char}.wav path
Stack (Locked)

Backend: Python FastAPI + Gemini 2.0 Flash Lite + Pydantic + Chatterbox TTS + SQLite + SQLModel
Frontend: Next.js 14 + Tailwind + Shadcn + Zustand + Framer Motion
Folder: /data (2 bibles), /backend/app (main.py, types.py, prompt_builder.py, llm_caller.py, merge_turn.py, audio_service.py), /frontend/src/components
What Opencode Should Do First

    Build /backend/app/types.py from bible schemas (Pydantic models)
    Build prompt_builder.py with 3 exact system prompts (from docs)
    Build llm_caller.py with Gemini calls + Pydantic validation retry
    Build merge_turn.py
    Test with: POST /api/turn with fake player input, console.log final JSON
    Only then build frontend components

Do NOT build UI first. JSON contract must be stable first.