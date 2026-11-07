# Implementation status — 7 November 2026

The repository originally contained specifications only. It now includes a runnable Python application, an Indonesian responsive web interface, configuration templates, Docker services and automated tests.

Implemented: cookie authentication and registration, development seed/login, owned UUID sessions, CV text/PDF validation and cleaning, long-document chunking, personalized question preparation, OpenAI transcription, ElevenLabs speech/cache/retries, bounded follow-ups, streamed answer transcripts, idempotent answer resubmission, room start/close/finish transitions, rubric snapshots, evidence verification, weighted scoring, review, result comparison, dashboard and history. The room checks camera frames, microphone signal and human-confirmed speaker output, and supports local mirror and optional fullscreen.

The latest November 5 updates take precedence over older examples in the reference documents. Scores are stored on a 1–5 scale and displayed as 0–100. Technical competency has zero HR weight. Mixed-language answers are accepted. Live sessions require provider credentials; there is no mock runtime mode.

Update 7 November: interview duration, follow-up budgets/enabling, and retry limits now read environment configuration and are preserved per session. The response timeout covers both LLM and live speech generation after transcription. MP3 format affects the speech request/cache; language hints are sent only to compatible models. Unsupported provider selections fail startup. Provider HTTP failures are translated into safe messages for invalid credentials, access restrictions, quota exhaustion and service errors without exposing remote response bodies.

## Differences from the reference design

- Evaluation currently runs in the finalization job after all answers are submitted, rather than overlapping individual evaluations with the conversation. The evaluator still groups each main answer with its follow-up and applies the snapshot rubric.
- Question variation uses nine seeded angles across the persona-specific prompts and seven slots. The claimed historical set of 61 angles was not supplied with the docs and is not reproduced as an unsupported claim.
- Evidence matching is conservative normalized exact text matching, rather than fuzzy matching. Scores with no valid quotation are capped at 2/5. The trade-off is that slightly altered quotations may be rejected.
- Original PDF and candidate answer audio are not persisted. PDF extraction and transcription use upload/request memory; clean CV text is retained. No raw answer-audio deletion job is needed.
- SQLAlchemy uses portable JSON and integer keys, including on PostgreSQL. Schema creation is automatic; production schema migrations and the historical `sql/01_schema.sql` were not supplied.
- TTS is ElevenLabs-only and STT is OpenAI-only. Legacy alternate-provider settings in old docs do not activate fallbacks.
- Runtime emits request IDs, AI usage and failure-type events. It does not yet implement every historical timer or cost-estimation log field.
- The setup form starts empty apart from account profile values; no automatically inserted dummy CV/JD.
- Browser UI uses CSS bars for competencies instead of Chart.js. Dashboard API includes competency history; the UI shows aggregate stats and recent sessions.

## Validation and operations

The 21 automated regression tests inject provider responses and use a temporary SQLite database. They cover configuration limits/snapshots, retry enforcement, response timeout cancellation, MP3 cache settings, provider error redaction, and the core session flow. PostgreSQL, Redis/arq and Docker configuration require infrastructure integration testing. In-process jobs are development-only and do not survive process termination. PostgreSQL row locks serialize concurrent turns across web processes; local locks also serialize answer work in the SQLite development server. Use PostgreSQL plus Redis for production.

Chrome smoke verification passed for login, responsive dashboard (390/768/1440px), session setup, synthetic camera/microphone checks, three recorded and streamed answers, finalization and desktop/mobile results. Screenshots are in `artifacts/`. Device signals were synthetic; physical speaker confirmation, real accents and assessment quality remain manual checks.

The opt-in `tests/live_smoke.py --run-paid` performs a three-question interview against real configured APIs, including synthetic spoken answers and STT. It uses a temporary database and audio directory, leaves user sessions untouched, and records a non-secret diagnostic summary in `artifacts/live-smoke.json`. This command consumes provider credits and is excluded from automatic test discovery.

Live verification passed on 7 November 2026: all three configured ElevenLabs voice IDs were accessible; a three-question HR session completed through real question generation, five prepared audio files, three synthesized candidate answers, OpenAI transcription, streamed AI responses, and final scoring/review. The synthetic session scored 3.64/5 (four measured competencies) and completed in 49.74 seconds; this automated timing excludes human recording time and is not a latency guarantee. User/Manager voice access was checked, but full interviews for those personas and adaptive follow-up were not exercised by this live run. Follow-up behavior remains covered by injected-provider tests. The temporary test records/audio were removed at completion; the report contains no API keys or candidate documents.

The Nginx file is an HTTP proxy example for an HTTPS ingress, not a bundled certificate setup. Camera/microphone require HTTPS outside localhost. Keep `.env` and persisted data out of source control. Existing methodology documents still describe the broader intended system; this file records the implemented scope.
