
**1.
 Player Setup Module World selection + character creation - player 
defines name, goal, personality, background, starting position.**

INPUT:

Nothing - it's the first screen. User types in UI.

UI fields user fills:

- world_name: string
- character_name, goal, personality, background, starting_position: string

OUTPUT JSON:

This JSON is saved and passed to Piece 4 (Prompt Builder)

```jsx
{
"player": {
"world_choice": "Death Note",
"character_name": "Jay",
"goal": "Prove Light is Kira without dying",
"personality": "Paranoid, observant, uses humor to deflect",
"background": "Transfer student, ex-detective assistant",
"starting_position": "In class next to Light, L is watching",
"own_plan": "" // Empty at start, player will make it during gameplay
"timestamp": "2026-05-13T10:00:00Z"
},

```

**2.
 World Concept JSON The chosen world as JSON - all canon characters 
defined as autonomous players, each with their own knowledge, 
motivation, goal, and living stats.**

INPUT:

```jsx
{
"world_choice": "Death Note"
}
```

OUTPUT:

The full bible JSON I sent you. That file already exists on your server as death_note_bible.json. We just LOAD it. We don't call LLM to make it.

If
 you WANT LLM to generate new worlds automatically in future (like user 
types "Naruto" and we have no bible), then INPUT to LLM would be:

```json
{
"world": {
"name": "Death Note",
"canon_summary":

"Light just started killing criminals. L broadcasted as Lind L Tailor

and figured out Kira lives in Kanto region. Investigation is starting in

schools.",
"rules": "Death Note kills in 40 sec if name+face known. Shinigami exists. L hides identity."
},
"autonomous_players": [
{
"id": "L",
"canon_name": "L Lawliet",
"type": "autonomous_player",
"dialogue_style": {
"vocab": ["Probability", "Hypothesis", "Conjecture", "5% chance", "If you were Kira..."],
"speech_pattern":

"Speaks low, eats sweets, never makes direct accusations. Example:

'That is an interesting defense, Jay. There is a 73% chance you are

hiding something.'",
"never_says": "He never yells, never says 'I think' always 'I suspect'"
},
"planning_framework": {
"type": "Elimination via controlled test",
"how_he_plans": "Creates a fake scenario with limited variables to force a reaction that confirms or denies a hypothesis"
},
"starting_plan": {
"objective": "Determine if new transfer student Jay is connected to Kira",
"plan": "Mention Kira's Kanto broadcast in class and observe reactions"
},
"stats": {
"suspicion_towards_player": 50,
"trust_towards_player": 20,
"voice_id": "L_chatterbox"
}
},
{
"id": "LIGHT",
"canon_name": "Light Yagami",
"dialogue_style": {
"vocab": ["Justice", "Perfect world", "I am..."],
"speech_pattern": "Charismatic, confident, speaks like he is always right. Example: 'Kira is doing what is right. The world is rotten.'",
"never_says": "Never shows doubt, never stutters"
},
"planning_framework": {
"type": "Manipulation via false trust",
"how_he_plans": "Befriends person to use them as pawn, gives them small secrets to gain loyalty"
},
"starting_plan": {
"objective": "Find out if Jay can be useful",
"plan": "Act friendly since Jay is being trolled, gain trust"
},
"stats": {
"suspicion_towards_player": 20,
"trust_towards_player": 40,
"voice_id": "light_chatterbox"
}
}
],
"developer_context": {
"game_rules": "All characters are autonomous players trying to win. Never break character. Never reveal AI.",
"never_split": "Evaluate player message for Chris Voss tactics. Characters use Mirroring, Labeling.",
"output_mandate": "Must output valid JSON only."
}
}
```

**3. Skill Engine Never Split the Difference tactics as the core mechanic - how mirroring, labeling, accusation audit etc are evaluated as valid moves.**

INPUT

```json
{
"skill_book_choice":"Never Split the Difference"
}
```

OUTPUT

```json
{
"book": "Never Split the Difference",
"skills": [
{
"id": "MIRRORING",
"name": "Mirroring",
"definition": "Repeat last 1-3 key words of opponent to get them to elaborate",
"example_good": "Player: 'I am alone here' -> L: 'Alone here?'",
"example_bad": "Full sentence repeat",
"how_to_detect": "Check if response contains exact 1-3 words from previous speaker's last sentence",
"game_effect": "If used correctly, lowers suspicion by 10, increases trust by 10. Target reveals more info"
},
{
"id": "LABELING",
"name": "Labeling",
"definition": "Name the emotion - start with 'It seems like...' / 'It looks like...'",
"example_good": "It seems like you're angry because your father was framed",
"example_bad": "You are angry (direct accusation)",
"how_to_detect": "Starts with 'It seems like' / 'It looks like' / 'It sounds like' + emotion word",
"game_effect": "If correct emotion, trust +15, stress -10. If wrong, trust -10"
},
{
"id": "ACCUSATION_AUDIT",
"name": "Accusation Audit",
"definition": "List worst things opponent could think about you before they say it",
"example_good": "You probably think I'm just a transfer student trying to get attention after my dad's case",
"how_to_detect": "Starts with 'You probably think...' / 'You might think I'm...' listing negatives",
"game_effect": "Large trust boost +20 if vulnerable and honest"
},
{
"id": "CALIBRATED_QUESTION",
"name": "Calibrated Question",
"definition": "How/What questions that make opponent feel in control",
"example_good": "How am I supposed to trust Kira's justice after what happened to my father?",
"how_to_detect": "Question starts with How or What",
"game_effect": "Forces autonomous player to answer and reveal plan piece"
}
],
"scoring": {
"level_up_rule": "If player uses 3 correct tactics in a row, autonomous player's suspicion drops significantly"
}
}
```

**4.Single-Request Prompt Builder Takes Player Setup + World Concept + 
current conversation history and builds ONE prompt that forces the LLM 
to play all autonomous characters.**

Final locked version for your 3 LLM Requests:

### **REQUEST 1: Listener / Teacher**

**INPUT:**

```json
{
  "skill_bible": "Full Never Split bible - MIRRORING, LABELING, ACCUSATION_AUDIT, CALIBRATED_QUESTION with how_to_detect + intended_effect",
  "player": {
    "background": "Father framed, killed by Kira, revenge, scholarship, trolled in class",
    "goal": "Find Kira"
  },
  "mission_context": {
    "current_mission": { "id": 3, "title": "Gain L's attention", "description": "After Kanto broadcast, class discussing" },
    "old_missions_summary": ["M1 Completed: Survived trolling", "M2 Failed: Asked Light directly about Kira"],
    "full_conversation_this_mission": [ { "speaker": "L", "text": "..." }, { "speaker": "Jay", "text": "..." } ]
  },
  "new_player_input": "You probably think I'm just making up my father story..."
}
```

```
You are the Skill Evaluator for a Never Split the Difference learning game.
Your job:
- Read player input and full conversation of this mission.
- Detect if player used MIRRORING, LABELING, ACCUSATION_AUDIT, CALIBRATED_QUESTION using how_to_detect from skill_bible.
- Judge how properly he used it considering his background.
- Never invent skills outside bible.
- Output ONLY JSON in format specified. No extra text.
```

**OUTPUT:**

```json
{
  "did_use_concept": true,
  "concepts_used": ["ACCUSATION_AUDIT"],
  "how_properly_used": "Perfect - listed worst thought before opponent, linked to father backstory",
  "player_intent": "Disarm suspicion, gain trust",
  "new_plan_proposed_by_player": false,
  "did_pass_this_turn": true,
  "feedback_for_player": "Great accusation audit, you disarmed L"
}
```

### **REQUEST 2: Character Brain - for EACH character in scene**

**INPUT:**

```json
{
  "scene_characters": {
    "source": "From mission.scene.characters_present - e.g. ['L', 'LIGHT']",
    "this_character_bible": { "id": "L", "dialogue_style": {}, "planning_framework": {}, "voice_id": "" },
    "this_character_current_plan": { "objective": "Test if Jay is linked to Kira", "plan": "Mention broadcast, observe reaction", "status": "ongoing" },
    "this_character_stats": { "suspicion": 50, "trust": 20 }
  },
  "mission_context": {
    "current_mission": { "title": "...", "location": "Class 3B" },
    "full_conversation_this_mission": []
  },
  "request_1_output": { "did_use_concept": true, "concepts_used": ["ACCUSATION_AUDIT"] }
}
```

```
You are {character_id} from Death Note.
Rules:
- You must speak EXACTLY in your dialogue_style - use vocab and example.
- You have a private plan and objective - think using planning_framework.
- You received analysis of player - his skill usage.
- If player used skill correctly, you must react positively and update stats delta as integer with reason. Decide delta based on YOUR personality, not fixed number.
- You must also set a challenge_for_player - which concept from Never Split he must use next to beat your dialogue.
- Never break character. Never mention you are AI.
- Output ONLY JSON for this one character.
```

**OUTPUT:**

```json
{
  "character_id": "L",
  "inner_thought": "He used audit, 60% chance honest about father, my test worked",
  "dialogue": "It seems like you're worried no one believes your father's innocence",
  "did_change_plan": false,
  "plan_status": "ongoing",
  "new_plan": null,
  "stat_changes": {
    "trust": { "delta": 15, "reason": "Vulnerability matched backstory" },
    "suspicion": { "delta": -10, "reason": "Disarmed my suspicion" }
  },
  "challenge_for_player": {
    "required_concept": "LABELING",
    "why": "L labeled Jay, Jay must label back or mirror to win trust"
  },
  "objective": "Test if Jay is linked to Kira",
  "how_plan_helps_objective": "Label forces him to elaborate on father case details"
}
```

### **REQUEST 3: Narrator / Mission Manager**

**INPUT:**

```json
{
  "world_lore": "Kanto broadcast just happened, school chaos",
  "player": { "full Piece 1 JSON" },
  "mission_chain": {
    "total_missions": 5,
    "completed": 2,
    "current_mission": { "id": 3, "title": "Gain L's attention", "why_important": "To join investigation" },
    "how_missions_interconnected": "M3 -> M4 join team -> M5 access L's data"
  },
  "request_1_output": {},
  "request_2_outputs": [ { "character_id": "L", "dialogue": "..." }, { "character_id": "LIGHT", "dialogue": "..." } ],
  "full_conversation_this_mission": []
}
```

```
You are the Narrator and Mission Manager.
Rules:
- You are not a character, you describe environment like anime narrator.
- Explain where player is, why he is there, context he doesn't have.
- You manage mission chain - decide if current mission won/lost based on Request 1 did_pass + Request 2 stat changes.
- If won, create next mission that logically connects to player goal.
- Track total/completed missions and why chain matters for player goal.
- Handle characters_entered/left if story needs.
- Output ONLY JSON.
```

**OUTPUT:**

```json
{
  "narration": "Classroom noisy after broadcast. Everyone looks at you because of father case. L watches from back eating candy.",
  "where": "Classroom 3B, after Lind L Tailor broadcast",
  "why_here": "You are here to prove father innocent and find Kira",
  "mission_status": {
    "current_mission_won": true,
    "need_new_mission": true,
    "next_mission": { "title": "Get L's contact", "why_important": "Only way to investigation team" },
    "chain_progress": "3/5 completed"
  },
  "scene_update": {
    "characters_entered": [],
    "characters_left": [],
    "new_characters_present_for_next_turn": ["L", "LIGHT"]
  }
}
```

This is clean GIGO-safe. Each LLM gets only what its job needs.

**6 UI + Audio Renderer
Frontend that takes that Game Turn JSON, renders living characters, animates stat meters, and sends voice tags to Chatterbox for real character voices.**

### All Components Needed - Final List:

Layout Shell:

1. `GamePage` - Main container
2. `TopBar` - Mission progress + Audio toggle + Coach button

Chat Area:

3. `ChatContainer` - Scrollable list

4. `NarrationBubble` - Italic grey system text (from Request 3)

5. `CharacterMessage` - PFP + Name + Dialogue bubble + Audio play + Voice tag

6. `PlayerMessage` - Your PFP + Your input + Skill feedback tag

7. `SkillFeedbackTag` - Green/Red pill: "✓ ACCUSATION_AUDIT Perfect"

Inspector:

8. `CharacterInspectorDrawer` - Right side slide

9. `PFP` - Reusable avatar

10. `StatBar` - Trust/Suspicion bar with delta animation

11. `MemoryList` - List of what they remember about you

12. `InnerThought` - Blurred box, click to reveal

Input:

13. `ChallengeHint` - Small text above input "L expects LABELING"

14. `InputBar` - Text field + Send button

Modals:

15. `CoachModal` - Explains current required concept with example from chat

16. `AudioButton` - Global mute + per-message play

Total: 16 
components, but core is only 5: ChatContainer, CharacterMessage, 
InputBar, CharacterInspectorDrawer, TopBar. Rest are sub-components.

Build order: `GamePage
 -> ChatContainer -> CharacterMessage/PlayerMessage -> InputBar
 -> CharacterInspectorDrawer -> CoachModal -> AudioButton`

### **6B Audio Renderer - Locked:**

**INPUT:**

```json
{
  "character_id": "L",
  "dialogue": "It seems like you're worried no one believes your father's innocence"
}
```

**SYSTEM:**

- You have folder: `/audio_samples/`
    - `L.wav` - 10 sec sample of L voice
    - `LIGHT.wav` - sample
    - `MISA.wav` etc
- Map character_id -> sample path + voice_id (if Chatterbox needs)

**PROCESS:**

```
1. Load /audio_samples/{character_id}.wav as reference
2. chatterbox.clone( reference_audio, text: dialogue )
3. Save output to /generated_audio/{turn_id}_{character_id}.wav
```

**OUTPUT:**

```json
{
  "character_id": "L",
  "audio_path": "/generated_audio/12_L.wav",
  "duration": 3.2
}
```

Frontend just does: `<audio src={audio_path} autoplay />`

**No voice_tag needed anymore** if you are cloning - sample already has character voice character. Tags only if you want emotion control, but Chatterbox will infer from text.

For MVP:

- Input: character + dialogue
- Output: wav path

That's it. One function `generateVoice(character_id, dialogue) -> audio_path`

Want to lock this and move to coding?