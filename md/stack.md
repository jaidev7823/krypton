Updated stack - Python version:

**Backend:**
```
Python + FastAPI - single service for LLM + Audio
Direct Gemini API calls - google-generativeai SDK, 3 prompts only
LLM: gemini-2.0-flash-lite (or gemini-1.5-flash for cheaper)
Pydantic - validate LLM JSON output, auto retry if invalid (same as Zod)
```

**Frontend:**
```
Next.js 14 + Tailwind + Shadcn - Suzerain chat style
State: Zustand - store final merged JSON + audio_path
Animations: Framer Motion for stat bars delta
```

**Audio (same service):**
```
Chatterbox TTS inside FastAPI - no separate service
Endpoint: POST /api/audio {character_id, dialogue}
Loads /audio_samples/{id}.wav, clones, saves to /generated_audio/
Returns: {audio_path, duration}
Store: /static/generated_audio/
```

**DB:**
```
SQLite + SQLModel (Pydantic ORM) - save player_setup, conversation history, character memory
```

**Folder for opencode:**
```
/data - death_note_bible.json + never_split_bible.json
/backend/
  /app/
    main.py - FastAPI app
    types.py - Pydantic models for all JSONs
    prompt_builder.py - 3 prompt builders
    llm_caller.py - 3 Gemini calls
    merge_turn.py - merge R1+R2+R3 -> final Game Turn JSON
    audio_service.py - chatterbox clone
    db.py - SQLite
  /audio_samples/world_name/ - L.wav, LIGHT.wav
  /generated_audio/ - output wavs
/frontend/
  /src/app/ - Next.js
  /src/components/ - 16 components (GamePage, ChatContainer, etc)
  /src/lib/ - api client to FastAPI
  /src/store/ - Zustand store
```

**API Contract:**
```
POST /api/turn
Input: {player_setup, conversation_history, new_player_input, mission_id}
Output: Final Game Turn JSON (Piece 5)

POST /api/audio
Input: {character_id, dialogue}
Output: {audio_path}
```

One backend, one frontend. Opencode can build backend first, test with curl, then frontend.
