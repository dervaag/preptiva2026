# Preptiva

AI interview practice built from the specifications in `docs/`: FastAPI, async SQLAlchemy, Jinja2, vanilla JavaScript, OpenAI and ElevenLabs. Indonesian UI with Indonesian or English interview sessions.

Interviews now support CV-grounded questions, academic/project experience for fresh graduates, adaptive next questions, and panels of two or three interviewers with separate HR/User/Manager scopes. See the [question guidebook](docs/question-guidebook.md) for role boundaries, methodology and limitations.

## Run locally

Use Python 3.12, matching Docker and CI. LangGraph requires Python 3.10 or newer; an old Python 3.9 virtualenv must be recreated with Python 3.12 before installing these dependencies.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m app.scripts.seed
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000. Demo login: `demo@interview.local` / `demo1234`. `/dev-login` is only available in development after seeding. Account registration, dashboard and history work without AI credentials. To create a real interview, set `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` and the chosen persona's `ELEVENLABS_VOICE_*` ID in `.env`. The application never substitutes dummy interviews or browser speech.

The browser uses a local camera preview and supports audio or text answers. Candidate CV/JD and transcripts are sent to AI providers. Answer audio is held in request memory rather than persisted; transcripts, generated interviewer audio and evaluations remain on the server. Tab/offline/device interruption stops the active question and offers Retry/Next; explicit exit closes the session. Use localhost or HTTPS for camera/microphone access.

Optional LangGraph orchestration covers preparation, each interview turn, and finalization. Set `ORCHESTRATION_ENGINE=langgraph` for new sessions; the default remains `legacy`, and existing sessions retain their engine. See [graph operations and rollout](docs/langgraph-orchestration.md) for persistent checkpoints, versioned panel scoring, recovery and synthetic baseline measurements.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check app/static/js/app.js
node --check app/static/js/interview-room.js
```

Tests use a temporary database and injected provider responses. They never call paid providers. Live voice quality and physical camera/speaker behavior require a configured manual session.

Optional Chrome smoke test: install `playwright` in the virtualenv and run `.venv/bin/python tests/browser_smoke.py` with Google Chrome installed. For the graph backend run `tests/graph_browser_smoke.py panel`, `voice` or `realtime`. These use temporary data and synthetic providers; set `PREPTIVA_BROWSER_ARTIFACTS=/tmp/preptiva-smoke` to retain reports/screenshots.

An explicit live-provider check is also available: `.venv/bin/python tests/live_smoke.py --run-paid`. It consumes real API credits, uses synthetic documents/answers with an isolated temporary database, and saves a diagnostic summary to `artifacts/live-smoke.json`. It checks configured voice access, question preparation, ElevenLabs speech, OpenAI transcription, streamed responses and scoring. Restart the app after changing `.env`; see [active environment settings](docs/env.md#status-implementasi-7-november-2026).

## Deployment

Untuk Kiri lokal, jalankan `sh deploy/kiri.sh up`, lalu buka **https://preptiva.kiri.local**. Konfigurasi terpisah ada di `compose.kiri.yaml`; helper membuat `.env.kiri` dengan secret acak tanpa mengubah `.env` development. Lihat [panduan Kiri](docs/deployment-kiri.md) untuk pengaturan HTTPS, data PostgreSQL, dan operasional.

Auto-deploy ke satu Mac Kiri sudah aktif dan teruji melalui `.github/workflows/kiri.yml`: tes pada GitHub, lalu deployment commit `main` pada runner khusus `preptiva-kiri-bima`. Teman dapat push branch lalu merge PR ke `main`; lihat [aktivasi dan alur kolaborasi](docs/deployment-kiri.md#deployment-otomatis-hanya-mac-bima). Environment deployment disimpan lokal, terpisah dari checkout; volume PostgreSQL/Redis tetap digunakan saat aplikasi diperbarui.

Akses internet tersedia melalui [Kiri Share](docs/deployment-kiri.md#akses-publik-melalui-kiri-share), yang meneruskan URL HTTPS publik ke web pada `127.0.0.1:18080`. URL Share bergantung pada sesi dan proses tunnel harus tetap berjalan; PostgreSQL/Redis tidak dipublish langsung.

Autostart Share sudah dipasang untuk akun Mac ini. Jalankan `python3 deploy/kiri_share_service.py status` untuk melihat URL terbaru. Layanan mulai setelah login macOS, memulihkan proses Share, dan memperbarui origin aplikasi ketika URL berubah.

The supplied Python backend runs locally or with Docker, PostgreSQL and an arq/Redis worker. It does not target Cloudflare Workers/Sites hosting. Set a random 32+ character secret and secure cookies in production, and terminate HTTPS at your ingress. Then run `docker compose up -d --build`. The web service binds to loopback port 8000. `deploy/nginx.conf` is an HTTP proxy reference; configure certificates at your ingress before production use. Set `DB_PASSWORD` for Compose. Provider settings are passed through `.env`; never commit it.

See [implementation status](docs/implementation-status.md) for differences from the broader reference design and remaining validation work.

Pemulihan pertanyaan dan context packet: [status brief panel](docs/panel-implementation.md). Persiapan pembandingan skor manusia: [validasi asesor](docs/assessor-validation.md).

## External answer-grading benchmark

[Mohler ASAG](docs/mohler-benchmark.md) is available locally as a separate benchmark: 2,442 human-rated answers and a 50-answer pilot. The importer preserves original scores, flags 214 inconsistent source averages and excludes them from pilot selection. Data stays under ignored `data/external/`; it is not included in a fresh clone or deployment image. Re-download using the pinned-revision command in the guide.

The benchmark uses a separate reference-based grading prompt through the application's model client. It does not change interview scoring or validate the production evaluator. Model evaluation has not been run; there are no AI–human benchmark metrics yet. Running it requires `OPENAI_API_KEY`, `MODEL_DEEP` and the explicit `--run-paid` flag. Optional Parquet dependencies are in `validation/requirements.txt`. See [initial verification results](docs/validation-initial-report.md).
