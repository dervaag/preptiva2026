# Preptiva

AI interview practice built from the specifications in `docs/`: FastAPI, async SQLAlchemy, Jinja2, vanilla JavaScript, OpenAI and ElevenLabs. Indonesian UI with Indonesian or English interview sessions.

## Run locally

Python 3.12 recommended (the application is also tested with the available Python 3.9 runtime).

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m app.scripts.seed
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Visit http://localhost:8000. Demo login: `demo@interview.local` / `demo1234`. `/dev-login` is only available in development after seeding. Account registration, dashboard and history work without AI credentials. To create a real interview, set `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` and the chosen persona's `ELEVENLABS_VOICE_*` ID in `.env`. The application never substitutes dummy interviews or browser speech.

The browser uses a local camera preview and uploads audio answers only. Candidate CV/JD and transcripts are sent to AI providers. Answer audio is held in request memory rather than persisted; transcripts, generated interviewer audio and evaluations remain on the server. Leaving a running room closes the session. Use localhost or HTTPS for camera/microphone access.

## Checks

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check app/static/js/app.js
node --check app/static/js/interview-room.js
```

Tests use a temporary database and injected provider responses. They never call paid providers. Live voice quality and physical camera/speaker behavior require a configured manual session.

Optional Chrome smoke test: install `playwright` in the virtualenv and run `.venv/bin/python tests/browser_smoke.py` with Google Chrome installed. It verifies a complete interview with synthetic devices and test-only provider responses, and writes screenshots under `artifacts/`.

An explicit live-provider check is also available: `.venv/bin/python tests/live_smoke.py --run-paid`. It consumes real API credits, uses synthetic documents/answers with an isolated temporary database, and saves a diagnostic summary to `artifacts/live-smoke.json`. It checks configured voice access, question preparation, ElevenLabs speech, OpenAI transcription, streamed responses and scoring. Restart the app after changing `.env`; see [active environment settings](docs/env.md#status-implementasi-7-november-2026).

## Deployment

Untuk Kiri lokal, jalankan `sh deploy/kiri.sh up`, lalu buka **https://preptiva.kiri.local**. Konfigurasi terpisah ada di `compose.kiri.yaml`; helper membuat `.env.kiri` dengan secret acak tanpa mengubah `.env` development. Lihat [panduan Kiri](docs/deployment-kiri.md) untuk pengaturan HTTPS, data PostgreSQL, dan operasional.

Auto-deploy ke satu Mac Kiri sudah aktif dan teruji melalui `.github/workflows/kiri.yml`: tes pada GitHub, lalu deployment commit `main` pada runner khusus `preptiva-kiri-bima`. Teman dapat push branch lalu merge PR ke `main`; lihat [aktivasi dan alur kolaborasi](docs/deployment-kiri.md#deployment-otomatis-hanya-mac-bima). Environment deployment disimpan lokal, terpisah dari checkout; volume PostgreSQL/Redis tetap digunakan saat aplikasi diperbarui.

Akses internet tersedia melalui [Kiri Share](docs/deployment-kiri.md#akses-publik-melalui-kiri-share), yang meneruskan URL HTTPS publik ke web pada `127.0.0.1:18080`. URL Share bergantung pada sesi dan proses tunnel harus tetap berjalan; PostgreSQL/Redis tidak dipublish langsung.

Autostart Share sudah dipasang untuk akun Mac ini. Jalankan `python3 deploy/kiri_share_service.py status` untuk melihat URL terbaru. Layanan mulai setelah login macOS, memulihkan proses Share, dan memperbarui origin aplikasi ketika URL berubah.

The supplied Python backend runs locally or with Docker, PostgreSQL and an arq/Redis worker. It does not target Cloudflare Workers/Sites hosting. Set a random 32+ character secret and secure cookies in production, and terminate HTTPS at your ingress. Then run `docker compose up -d --build`. The web service binds to loopback port 8000. `deploy/nginx.conf` is an HTTP proxy reference; configure certificates at your ingress before production use. Set `DB_PASSWORD` for Compose. Provider settings are passed through `.env`; never commit it.

See [implementation status](docs/implementation-status.md) for differences from the broader reference design and remaining validation work.
