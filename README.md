# AI-Onboard

Onboarding system for [AI-Knowledge](https://github.com/hsrambo07/AI-Knowledge) — a self-personalizing Twitter engagement agent. Runs a ~20-minute Claude-powered interview that extracts your voice, domain expertise, emotional register, and Twitter strategy, then generates every memory file the agent depends on and produces a ready-to-run `~/Desktop/AI-{handle}/` instance.

**The onboarding is the cold start.** Every downstream skill — reply generation, tweet ranking, query construction, emotional calibration — reads from memory files. Shallow files = generic output. This system treats onboarding as the most important session you'll ever have.

---

## How it works

```
python onboard.py
      │
      ├─ Phase 0: API key setup + Twitter browser login (Python-handled)
      │
      └─ Claude-powered interview (~20 min)
            │
            ├─ Phase 1: Identity foundation — role, company, unfair advantage
            ├─ Phase 2: Personal life + interests — lifestyle, hobbies, local context
            ├─ Phase 3: Voice capture — 3 domain-specific tweet scenarios → style analysis
            ├─ Phase 4: Domain + expertise → keyword banks + brand pillars
            ├─ Phase 5: Emotional register → per-topic sentiment map
            ├─ Phase 6: Twitter strategy + brand goals
            └─ Phase 7: Review + quality gates + soul map seed
                  │
                  └─ [INTERVIEW_COMPLETE] signal
                        │
                        ├─ Dedicated JSON generation call (16k token budget)
                        ├─ memory_gen.py → generates all memory files via Claude
                        ├─ patcher.py → copies + patches AI-Knowledge codebase
                        └─ ~/Desktop/AI-{handle}/ ready to run
```

**Claude IS the interviewer.** It conducts the full conversation naturally — no phase announcements, no forms. It tracks coverage internally, pushes for depth when answers are surface-level, uses earlier answers in later questions, and at the end outputs a complete structured JSON.

**Context is managed throughout.** The conversation history is preserved in full across the 200k token window. If an interview runs unusually long (>320k chars), older turns are compressed into a dense summary automatically. The final JSON is always generated in a separate dedicated call with a 16k token budget — it is never truncated regardless of interview length.

---

## Prerequisites

- Python 3.9+
- [AI-Knowledge](https://github.com/hsrambo07/AI-Knowledge) cloned to `~/Desktop/AI-Knowledge`
- An [Anthropic API key](https://console.anthropic.com)
- Chrome browser (for Twitter sessions)

## Setup

```bash
cd ~/Desktop/AI-Onboard
pip install -r requirements.txt
```

## Usage

**Full onboarding** (new user):
```bash
python onboard.py
```

**Resume from saved interview** (skip interview, redo codebase copy + memory generation):
```bash
python onboard.py --resume <handle>
```

**Regenerate memory files only** (re-run Claude generation on saved interview data):
```bash
python onboard.py --regen <handle>
```

---

## What the interview captures

| Phase | What Claude extracts | ~Time |
|-------|---------------------|-------|
| 1 | Role (exact), daily work, unfair advantage, career context, location, background | 2 min |
| 2 | Personal interests (specific), sports, travel, local scene, cultural touchstones | 2 min |
| 3 | Voice via 3 domain-specific tweet replies → rules, patterns, anti-patterns | 5–7 min |
| 4 | Domain expertise, hot takes → keyword banks (7 categories, 15–25 terms each) | 2 min |
| 5 | Per-topic emotional register — how each topic shows up in writing | 2 min |
| 6 | Twitter goals, target audience, content pillars, 5–10 target accounts, cringe definition | 3 min |
| 7 | Summary confirmation + quality gates + soul map synthesis | 2 min |

**Phase 3 is the most important.** Voice is captured through demonstration — you reply to 3 tweets Claude generates specifically for your domain. Claude analyzes what you actually wrote, not how you describe your style.

**Quality gates before completion:** Claude checks internally that each critical file has enough signal (≥5 specific identity facts, ≥5 concrete voice rules, ≥4 sentiment entries, ≥15 keywords per primary pillar). If any gate fails, it goes back and asks more.

---

## Memory files generated

All written into `~/Desktop/AI-{handle}/memories/`:

| File | How it's generated | Token budget |
|------|--------------------|-------------|
| `identity.md` | Claude — role, unfair advantage, career context, background | 2,000 |
| `writing_voice.md` | Claude — voice rules, named patterns, anti-patterns from actual replies | 3,000 |
| `sentiment_map.md` | Claude — per-topic emotional register + how each emotion shows in writing | 2,000 |
| `preferences.md` | Claude — content filters, engage/skip topics, session settings | 1,200 |
| `brand_goals.md` | Claude — north star, 6-month vision, target audience, content pillars | 1,500 |
| `career.md` | Claude — background, goals, skills | 1,500 |
| `soul_map.md` | Claude — full 6-dimension psychological profile (not a stub) | 6,000 |
| `twitter_target_list.md` | Generated from Phase 6 target accounts | — |
| `platforms/twitter/strategy.md` | Claude — per-pillar keyword banks with locked minimums, reply angles | 4,000 |
| `platforms/twitter/interaction_preferences.md` | Template, grows from sessions | — |
| `platforms/twitter/brand_learning.md` | Empty, grows from sessions (2 most recent parsed per tweet) | — |
| `writing_learned.md` | Empty, grows when you edit AI drafts (10 most recent injected per tweet) | — |
| `archive/learning_journal.md` | Stub for execution logs — excluded from memory index | — |
| `index.md` | Registry of all active memory files | — |

**Also generated:**
- `user_profile.json` — structured profile for the patcher (keyword banks, content pillars, brand pillars, soul map data)
- `.env` — your API key (never saved to interview JSON on disk)

### How memory feeds into every reply

AI-Knowledge uses a three-layer retrieval system — nothing is dumped raw into prompts:

```
TWEET ARRIVES
      │
      ├─ Smart extractor (no API call):
      │     writing_voice.md  → tweet-type-aware sections only
      │                          (humor tweet → Absurdist Pivot pattern injected)
      │                          (hot take → Authoritative-Humorous pattern injected)
      │                          + last 10 dated entries from writing_learned.md
      │     identity.md       → Core Facts + top 4 keyword-matched entries
      │     brand_learning.md → HIGH-TRACTION / WHAT'S FAILING from last 2 sessions only
      │
      ├─ Memory index retrieval (keyword scoring across all other files):
      │     soul_map, sentiment_map, interaction_preferences,
      │     preferences, strategy, brand_goals, career
      │     → top 7 sections, capped at 3,000 chars
      │     → auto-rebuilds index whenever any .md file changes
      │
      └─ Total context injected: ~5,000–7,000 chars of the most relevant content
```

### Soul map — 6 dimensions

Generated during onboarding from the full interview, not from a separate command:

1. **Idiographic Research** — what makes you uniquely you
2. **Single-Subject Design** — observable behavioral patterns
3. **Psychobiography** — life narrative arc and formative themes
4. **Functional Behavioral Assessment** — motivations behind your behaviors
5. **Communication Profile** — how to talk TO you; what framing you respond to
6. **AI Working Guide** — how the AI should work WITH you

Sections 5 and 6 feed directly into tone calibration for every reply session.

---

## After onboarding

```bash
cd ~/Desktop/AI-<handle>

# Sync your Twitter profile (reads tweets, replies, likes)
python run.py profile-sync --tweets 30 --replies 30 --likes 30

# Build psychological profile (rebuilds from all memory files)
python run.py soul-map

# Test session — no actual posting
python run.py skill twitter_browser --dry-run

# Real session
python run.py skill twitter_browser --real
```

After a few sessions:
```bash
python run.py consolidate-memory   # deduplicate memory entries (7-day cooldown, 55% Jaccard threshold)
python run.py soul-map --rebuild   # resynthesize as memories grow
```

**The system gets dramatically better after 2–3 sessions where you edit replies.** Your edits become permanent writing rules in `writing_learned.md`. The first few sessions are calibration — expect to edit a lot. That's it working as designed.

---

## Project structure

```
AI-Onboard/
├── onboard.py              # Entry point — full / resume / regen modes
├── requirements.txt
└── core/
    ├── interviewer.py      # Claude-powered 7-phase conversational interview
    │                       # Context management: rolling compression + dedicated JSON call
    ├── memory_gen.py       # Generates all memory files via Claude
    │                       # Section headers match AI-Knowledge memory_reader.py exactly
    └── patcher.py          # Copies + patches AI-Knowledge codebase
```

**Interview data** is saved to `.saved_interviews/<handle>.json` (API key excluded). Enables `--resume` and `--regen` without re-interviewing.

---

## What distinguishes good vs. shallow memory files

The difference is specificity. Claude is designed to push past surface answers.

**Shallow:**
> Role: Designer at a startup. Location: India.

**Rich:**
> Founding Product Designer at Entelligence — 12-person dev tools startup building AI-powered code review. Based in Koramangala, Bangalore. Sits between design and engineering; does Figma AND ships React. Unfair advantage: can engage credibly with design tool debates, AI coding tools, and startup operator questions from lived experience in all three roles.

**Shallow voice rule:**
> Be casual but professional.

**Rich voice rule:**
> Never open with sycophantic phrases. Start with a concrete observation or reframe. When disagreeing, lead with a specific experience — name the tool, the failure mode, the number. Not "I've seen this before" but "ran into this migrating our Figma tokens to CSS variables last month."
