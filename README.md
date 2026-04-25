# NadiNet — NGO Volunteer Coordination Platform

A full-stack, data-driven volunteer coordination platform for NGOs. NadiNet ingests community need signals from multiple channels, triangulates them into corroborated needs, scores and decays them by trust, matches volunteers algorithmically, and coordinates deployment via WhatsApp — all powered by Google Gemini AI.

---

## ⚡ Quickstart (3 commands)

```bash
cp .env.example .env          # Fill in GOOGLE_API_KEY, TWILIO credentials, JWT_SECRET
docker-compose up             # Starts db, backend, frontend, pgadmin
# (In a new terminal, after the backend is healthy:)
docker-compose exec backend python seed.py
```

Open **http://localhost:3000** — redirects to the dashboard.  
OpenAPI docs: **http://localhost:8000/docs**  
pgAdmin: **http://localhost:5050** (admin@nadinet.dev / nadinet)

---

## 🏗 Architecture

```
frontend (Next.js 14)  →  /api/*  →  backend (FastAPI)  →  PostgreSQL/PostGIS
                                            ↓
                                    Google Gemini AI (classification + embeddings)
                                    Google Vision API (OCR)
                                    Twilio WhatsApp API
                                    APScheduler (3 cron jobs)
```

### Core Engines

| Engine | File | Description |
|--------|------|-------------|
| NLP Classifier | `services/nlp_classifier.py` | Gemini 1.5-flash with cosine-similarity few-shot injection |
| Triangulation | `services/triangulation.py` | Corroboration state machine; C = (source_diversity + temporal + independence + geographic) / 2.5 |
| Priority Scoring | `services/scoring.py` | Score = F × U × G × V × C × T × 100 |
| Trust Decay | `services/decay.py` | T(t) = T₀ × e^(−λt), with reporter-trust modifiers |
| Matching | `services/matching.py` | 3-pass: hard filter → proximity ranking → kinship optimization |
| Kinship Graph | `services/kinship.py` | PostgreSQL adjacency with recursive CTE depth-2 traversal |

---

## 🔧 Configuring Decay Constants

Edit `app/services/decay.py`, `HALF_LIVES` dictionary:

```python
HALF_LIVES = {
    "medical_access":   96,   # 4 days — urgency decays fastest
    "nutrition":        144,  # 6 days
    "water_sanitation": 288,  # 12 days
    "shelter":          336,  # 14 days
    # ... etc
}
```

λ is computed automatically as `ln(2) / half_life_hours`. The reporter trust modifier scales λ:
- Trust ≥ 0.85 → 40% slower decay (λ × 0.6)
- Trust 0.65–0.85 → base rate
- Trust < 0.65 → 30% faster decay (λ × 1.3)

---

## 🤖 Google AI Services

All three Google AI services use a single `GOOGLE_API_KEY` environment variable:

| Service | SDK | Usage |
|---------|-----|-------|
| **Gemini 1.5-flash** | `google-generativeai` | Field report classification, debrief signal extraction, reverification parsing |
| **text-embedding-004** | `google-generativeai` | Few-shot example similarity search (cosine) |
| **Cloud Vision API** | `google-cloud-vision` | OCR primary; pytesseract is the fallback |

Every Google API call is wrapped in a `try/except` that degrades gracefully:
- Classification failure → `confidence=0.0`, flagged for manual review
- OCR failure → pytesseract fallback
- Embedding failure → random unit vector (with warning log)

---

## 📚 Few-Shot Examples — Monthly Update

The few-shot classification system works as follows:

1. **Storage**: `backend/models/few_shot_examples.json` — up to 200 examples with `text`, `category`, `urgency`, `embedding`, and metadata.
2. **Monthly cron (1st of month, 03:00 UTC)**: Pulls coordinator-confirmed signals from the past 30 days, computes their `text-embedding-004` embeddings, and prepends them to the examples file.
3. **At inference time**: The top 5 most similar examples (by cosine similarity vs the query embedding) are injected into the Gemini prompt as few-shot context.
4. **Seeding**: `python seed.py` pre-populates 20 examples covering all 9 need categories in English and Hindi transliteration with placeholder random-unit-vector embeddings. Replace with real embeddings by running the retrain job.

---

## 🧪 Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest                          # Runs all 5 test files
pytest -v app/tests/test_decay.py   # Single file
```

Test coverage:
- `test_triangulation.py` — corroboration state machine (5 scenarios)
- `test_scoring.py` — F/U/G/V/C/T scoring with edge cases
- `test_decay.py` — exponential decay, trust modifiers, thresholds
- `test_matching.py` — 3-pass matching with kinship optimization
- `test_nlp_classifier.py` — Gemini parsing, caching, few-shot retrieval

All tests use mocks — no live API calls or DB connections required.

---

## 📱 WhatsApp Bot Flows

| Flow | Trigger | States |
|------|---------|--------|
| Field reporting | Any message from known reporter | `REPORTING` |
| Volunteer registration | New phone number | `REGISTERING_1` … `REGISTERING_5` |
| Task acceptance | Pending task message | `AWAITING_TASK` |
| Post-task debrief | Volunteer with completed task | `DEBRIEFING_1` … `DEBRIEFING_3` |

Configure your Twilio WhatsApp sandbox to POST to: `https://your-domain/api/v1/webhook/whatsapp`

---

## 📊 API Reference

Full OpenAPI docs at `/docs`. Key endpoints:

```
POST /api/v1/ingest              — Manual signal ingestion
POST /api/v1/ingest/csv          — CSV batch upload
GET  /api/v1/needs               — Ranked active needs
GET  /api/v1/needs/{id}/candidates — 3-pass matched volunteers
POST /api/v1/dispatch            — Create tasks + send WhatsApp
POST /api/v1/debrief             — Submit outcome
GET  /api/v1/dashboard/stats     — Metric card data
GET  /api/v1/dashboard/kinship   — Graph nodes + edges
GET  /api/v1/reports/monthly?format=pdf — Funder report
```
