"""
Seed script — populates NadiNet with realistic NGO field data:
  5 reporters, 8 volunteers, 4 kinship edges, 12 signals → 4 corroborated needs,
  6 historical tasks, 3 debriefs.
Run: python seed.py
"""
import asyncio
import json
import math
import random
import os
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# ──────────────────────────────────────────────────────────────
# Bootstrap path so we can import app modules
# ──────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.config import settings
from app.database import Base
from app.models.reporter import Reporter
from app.models.signal import Signal
from app.models.need import Need
from app.models.volunteer import Volunteer
from app.models.kinship import KinshipEdge
from app.models.task import Task
from app.models.debrief import Debrief

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSession_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def now_utc(offset_hours: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=offset_hours)


def random_unit_vec(dim: int = 768) -> list[float]:
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x ** 2 for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


# ──────────────────────────────────────────────────────────────
# Few-shot examples data (20 labeled samples, English + Hindi)
# ──────────────────────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    # English examples
    {"text": "There are 30 children in Zone 4 who haven't eaten in two days, their families have no food.", "category": "nutrition", "urgency": 5, "zone_id": "Zone 4", "population_est": 120, "confidence": 0.97, "reasoning": "Explicit mention of food deprivation for children."},
    {"text": "The water pipe in Block 7B has been broken for a week, no clean water available for ~200 residents.", "category": "water_sanitation", "urgency": 4, "zone_id": "Block 7B", "population_est": 200, "confidence": 0.95, "reasoning": "Infrastructure failure affecting water access."},
    {"text": "Old lady near the Dharavi junction, 78 years old, needs regular medicine but no family support.", "category": "elderly_care", "urgency": 3, "zone_id": "Dharavi", "population_est": 1, "confidence": 0.91, "reasoning": "Elderly person requiring ongoing medical and social support."},
    {"text": "Slum fire in Kurla East last night — 15 families displaced, need temporary shelter immediately.", "category": "shelter", "urgency": 5, "zone_id": "Kurla East", "population_est": 75, "confidence": 0.98, "reasoning": "Emergency displacement requiring immediate shelter."},
    {"text": "A young man in Zone 2 is showing signs of severe depression, self-harm threats reported by neighbors.", "category": "mental_health", "urgency": 4, "zone_id": "Zone 2", "population_est": 1, "confidence": 0.89, "reasoning": "Acute mental health crisis with self-harm risk."},
    {"text": "Kids in the Bandra slum can't attend school — no materials, fees due for 3 months.", "category": "education", "urgency": 2, "zone_id": "Bandra", "population_est": 25, "confidence": 0.88, "reasoning": "Education access barrier due to financial constraint."},
    {"text": "Three women near Andheri West lost their street vending license, need income support.", "category": "livelihood", "urgency": 3, "zone_id": "Andheri West", "population_est": 3, "confidence": 0.85, "reasoning": "Livelihood disruption for street vendors."},
    {"text": "Diabetic patient in Zone 6, out of insulin — can't afford refill, urgent medical need.", "category": "medical_access", "urgency": 5, "zone_id": "Zone 6", "population_est": 1, "confidence": 0.96, "reasoning": "Acute medical access need: lack of insulin is life-threatening."},
    {"text": "Flooding in Sion Koliwada — 50 households cut off, drinking water contaminated.", "category": "water_sanitation", "urgency": 5, "zone_id": "Sion Koliwada", "population_est": 250, "confidence": 0.97, "reasoning": "Flood-related water contamination emergency."},
    {"text": "TB patient in Govandi stopped treatment midway, community health worker unresponsive.", "category": "medical_access", "urgency": 4, "zone_id": "Govandi", "population_est": 1, "confidence": 0.92, "reasoning": "Incomplete TB treatment is a public health risk."},
    # Hindi transliteration examples
    {"text": "Zone 3 mein bachhon ko khana nahi mil raha, teen din se bhookhe hain, koi madad karo.", "category": "nutrition", "urgency": 5, "zone_id": "Zone 3", "population_est": 40, "confidence": 0.93, "reasoning": "Children without food for three days."},
    {"text": "Dharavi ke paas budhiya akele hai, dawai chahiye aur khana bhi nahi.", "category": "elderly_care", "urgency": 3, "zone_id": "Dharavi", "population_est": 1, "confidence": 0.88, "reasoning": "Elderly woman alone without food or medicine."},
    {"text": "Block 12 mein pani nahi aaya teen din se, sab log pareshan hain.", "category": "water_sanitation", "urgency": 4, "zone_id": "Block 12", "population_est": 100, "confidence": 0.90, "reasoning": "Three days without water in residential block."},
    {"text": "Kurla mein aag lagi, ghar jal gaye, log sadak par hain, raat ko reh nahi sakte.", "category": "shelter", "urgency": 5, "zone_id": "Kurla", "population_est": 60, "confidence": 0.96, "reasoning": "Fire destroyed homes, emergency shelter needed."},
    {"text": "Andheri mein ek ladka bahut dukhi hai, rota rehta hai, kuch galat kar sakta hai.", "category": "mental_health", "urgency": 4, "zone_id": "Andheri", "population_est": 1, "confidence": 0.86, "reasoning": "Mental health crisis with concerning behaviour."},
    {"text": "Bandra slum mein school fees nahi bhari, bacche school se bahar hain.", "category": "education", "urgency": 2, "zone_id": "Bandra", "population_est": 15, "confidence": 0.84, "reasoning": "Education exclusion due to unpaid fees."},
    {"text": "Govandi mein ek bandi ki TB ki dawai khatam ho gayi aur nai nahi aa rahi.", "category": "medical_access", "urgency": 4, "zone_id": "Govandi", "population_est": 1, "confidence": 0.91, "reasoning": "TB medicine ran out, treatment gap."},
    {"text": "Zone 5 mein rehri wale ko thela chhinn liya, abhi koi kamai nahi.", "category": "livelihood", "urgency": 3, "zone_id": "Zone 5", "population_est": 1, "confidence": 0.82, "reasoning": "Livelihood loss due to street cart confiscation."},
    {"text": "Sion mein barish ke baad naali ka paani ghar mein ghus gaya, saaf paani nahi.", "category": "water_sanitation", "urgency": 4, "zone_id": "Sion", "population_est": 30, "confidence": 0.89, "reasoning": "Sewage flooding contaminating water supply."},
    {"text": "Zone 8 mein 10 families ko ghar nahi, koi building tod di nagar palika ne.", "category": "shelter", "urgency": 4, "zone_id": "Zone 8", "population_est": 50, "confidence": 0.93, "reasoning": "Municipal demolition leaving families homeless."},
]


async def seed():
    print("🌱 Seeding NadiNet database...")

    async with AsyncSession_() as db:
        # ── REPORTERS ──────────────────────────────────────────
        reporters_data = [
            {"phone": "+919820001111", "name": "Kavita Sharma", "trust_score": 0.94, "reports_filed": 45, "reports_verified": 42},
            {"phone": "+919820002222", "name": "Rajan Mehta",   "trust_score": 0.88, "reports_filed": 30, "reports_verified": 26},
            {"phone": "+919820003333", "name": "Sunita Patil",  "trust_score": 0.79, "reports_filed": 22, "reports_verified": 17},
            {"phone": "+919820004444", "name": "Arjun Das",     "trust_score": 0.65, "reports_filed": 15, "reports_verified": 9},
            {"phone": "+919820005555", "name": "Meera Iyer",    "trust_score": 0.51, "reports_filed": 8,  "reports_verified": 4},
        ]
        reporters = []
        for rd in reporters_data:
            r = Reporter(**rd, decay_modifier=1.0)
            db.add(r)
            reporters.append(r)
        await db.flush()
        print(f"  ✓ Created {len(reporters)} reporters")

        # ── VOLUNTEERS ────────────────────────────────────────
        volunteers_data = [
            {"phone": "+919870001111", "name": "Amit Verma",    "skills": ["first_aid", "transport", "general"], "languages": ["hindi", "english"], "has_transport": True,  "zone_id": "Zone 4",      "trust_score": 0.92, "completion_rate": 0.95, "availability_schedule": {"mon": [{"start": "09:00", "end": "17:00"}], "tue": [{"start": "09:00", "end": "17:00"}], "wed": [{"start": "09:00", "end": "17:00"}], "thu": [{"start": "09:00", "end": "17:00"}], "fri": [{"start": "09:00", "end": "17:00"}]}, "location_wkt": "POINT(72.8777 19.0760)"},
            {"phone": "+919870002222", "name": "Priya Nair",    "skills": ["nutrition", "elder_care", "counseling"], "languages": ["hindi", "english", "marathi"], "has_transport": False, "zone_id": "Dharavi",     "trust_score": 0.88, "completion_rate": 0.90, "availability_schedule": {"mon": [{"start": "10:00", "end": "18:00"}], "wed": [{"start": "10:00", "end": "18:00"}], "fri": [{"start": "10:00", "end": "18:00"}]}, "location_wkt": "POINT(72.8513 19.0470)"},
            {"phone": "+919870003333", "name": "Suresh Kumar",  "skills": ["construction", "general", "transport"], "languages": ["hindi", "tamil"], "has_transport": True,  "zone_id": "Kurla East",  "trust_score": 0.75, "completion_rate": 0.82, "availability_schedule": {"tue": [{"start": "08:00", "end": "16:00"}], "thu": [{"start": "08:00", "end": "16:00"}], "sat": [{"start": "08:00", "end": "14:00"}]}, "location_wkt": "POINT(72.8794 19.0714)"},
            {"phone": "+919870004444", "name": "Fatima Sheikh", "skills": ["first_aid", "nutrition", "education"], "languages": ["hindi", "urdu", "english"], "has_transport": False, "zone_id": "Zone 6",      "trust_score": 0.85, "completion_rate": 0.93, "availability_schedule": {"mon": [{"start": "09:00", "end": "15:00"}], "wed": [{"start": "09:00", "end": "15:00"}], "fri": [{"start": "09:00", "end": "15:00"}], "sat": [{"start": "09:00", "end": "13:00"}]}, "location_wkt": "POINT(72.8614 19.0318)"},
            {"phone": "+919870005555", "name": "Rohit Joshi",   "skills": ["counseling", "mental_health", "general"], "languages": ["hindi", "english", "gujarati"], "has_transport": False, "zone_id": "Andheri West","trust_score": 0.79, "completion_rate": 0.85, "availability_schedule": {"mon": [{"start": "14:00", "end": "20:00"}], "tue": [{"start": "14:00", "end": "20:00"}], "thu": [{"start": "14:00", "end": "20:00"}], "fri": [{"start": "14:00", "end": "20:00"}]}, "location_wkt": "POINT(72.8369 19.1340)"},
            {"phone": "+919870006666", "name": "Lakshmi Rao",   "skills": ["elder_care", "nutrition", "first_aid"], "languages": ["hindi", "telugu", "english"], "has_transport": False, "zone_id": "Govandi",     "trust_score": 0.83, "completion_rate": 0.88, "availability_schedule": {"tue": [{"start": "09:00", "end": "17:00"}], "thu": [{"start": "09:00", "end": "17:00"}], "sat": [{"start": "09:00", "end": "17:00"}]}, "location_wkt": "POINT(72.9218 19.0536)"},
            {"phone": "+919870007777", "name": "Vikram Singh",  "skills": ["transport", "general", "construction"], "languages": ["hindi", "punjabi"], "has_transport": True,  "zone_id": "Block 7B",    "trust_score": 0.70, "completion_rate": 0.78, "availability_schedule": {"mon": [{"start": "06:00", "end": "14:00"}], "wed": [{"start": "06:00", "end": "14:00"}], "fri": [{"start": "06:00", "end": "14:00"}]}, "location_wkt": "POINT(72.8647 19.0596)"},
            {"phone": "+919870008888", "name": "Nandita Ghosh", "skills": ["education", "counseling", "nutrition"], "languages": ["hindi", "bengali", "english"], "has_transport": False, "zone_id": "Bandra",      "trust_score": 0.91, "completion_rate": 0.96, "availability_schedule": {"mon": [{"start": "10:00", "end": "18:00"}], "tue": [{"start": "10:00", "end": "18:00"}], "wed": [{"start": "10:00", "end": "18:00"}], "thu": [{"start": "10:00", "end": "18:00"}]}, "location_wkt": "POINT(72.8347 19.0596)"},
        ]
        volunteers = []
        for vd in volunteers_data:
            v = Volunteer(**vd, is_available=True)
            db.add(v)
            volunteers.append(v)
        await db.flush()
        print(f"  ✓ Created {len(volunteers)} volunteers")

        # ── KINSHIP EDGES ─────────────────────────────────────
        kinship_pairs = [
            (0, 1, 3, 0.93),  # Amit ↔ Priya, 3 co-deployments, high quality
            (1, 3, 2, 0.85),  # Priya ↔ Fatima, 2 co-deployments
            (0, 2, 4, 0.80),  # Amit ↔ Suresh, 4 co-deployments
            (4, 7, 1, 1.00),  # Rohit ↔ Nandita, 1 co-deployment
        ]
        for a_idx, b_idx, co_dep, quality in kinship_pairs:
            edge = KinshipEdge(
                volunteer_a_id=volunteers[a_idx].id,
                volunteer_b_id=volunteers[b_idx].id,
                co_deployments=co_dep,
                quality_score=quality,
                last_deployed=now_utc(72),
            )
            db.add(edge)
        await db.flush()
        print("  ✓ Created 4 kinship edges")

        # ── SIGNALS + NEEDS ────────────────────────────────────
        # 12 signals across 3 zones → 4 corroborated needs at different priority levels

        signal_specs = [
            # NEED 1: URGENT — medical_access in Zone 6 (score should be high)
            {"reporter": reporters[0], "channel": "whatsapp", "zone_id": "Zone 6", "category": "medical_access", "urgency": 5, "pop": 1,   "raw": "Diabetic patient out of insulin, can't afford refill, very urgent.",              "hours_ago": 5,   "conf": 0.96},
            {"reporter": reporters[1], "channel": "app",      "zone_id": "Zone 6", "category": "medical_access", "urgency": 5, "pop": 1,   "raw": "Emergency — man in Zone 6 has no insulin and is going into diabetic shock.",       "hours_ago": 4,   "conf": 0.97},
            {"reporter": reporters[2], "channel": "ocr",      "zone_id": "Zone 6", "category": "medical_access", "urgency": 4, "pop": 1,   "raw": "Handwritten note: insulin needed Zone 6 urgently old man very sick.",              "hours_ago": 6,   "conf": 0.88},
            # NEED 2: HIGH — nutrition in Zone 4
            {"reporter": reporters[1], "channel": "whatsapp", "zone_id": "Zone 4", "category": "nutrition",      "urgency": 4, "pop": 120, "raw": "Zone 4 mein bachhon ko khana nahi — 30 families, teen din se bhookhe hain.",       "hours_ago": 20,  "conf": 0.93},
            {"reporter": reporters[2], "channel": "app",      "zone_id": "Zone 4", "category": "nutrition",      "urgency": 4, "pop": 120, "raw": "Child malnutrition crisis in Zone 4, approx 30 children affected badly.",          "hours_ago": 18,  "conf": 0.92},
            {"reporter": reporters[3], "channel": "csv",      "zone_id": "Zone 4", "category": "nutrition",      "urgency": 3, "pop": 80,  "raw": "Food shortage reported, elderly and children most affected in Zone 4.",           "hours_ago": 12,  "conf": 0.85},
            # NEED 3: MEDIUM — shelter in Kurla East
            {"reporter": reporters[2], "channel": "whatsapp", "zone_id": "Kurla East", "category": "shelter", "urgency": 3, "pop": 30,  "raw": "Families in Kurla East need temporary shelter after building demolished.",          "hours_ago": 48,  "conf": 0.88},
            {"reporter": reporters[3], "channel": "app",      "zone_id": "Kurla East", "category": "shelter", "urgency": 3, "pop": 25,  "raw": "15 families displaced after Kurla East building collapse, no shelter.",              "hours_ago": 50,  "conf": 0.87},
            # NEED 4: LOW — water_sanitation in Block 7B (older signals, decayed)
            {"reporter": reporters[3], "channel": "csv",      "zone_id": "Block 7B", "category": "water_sanitation", "urgency": 2, "pop": 200, "raw": "Water pipe broken in Block 7B — no clean water for ~200 residents since Monday.", "hours_ago": 120, "conf": 0.90},
            {"reporter": reporters[4], "channel": "whatsapp", "zone_id": "Block 7B", "category": "water_sanitation", "urgency": 2, "pop": 200, "raw": "Block 7B pani nahi aa raha, pipe toot gayi, ek hafte se zyada ho gaya.",         "hours_ago": 118, "conf": 0.88},
            # Watch-only signals (no corroboration yet)
            {"reporter": reporters[4], "channel": "whatsapp", "zone_id": "Govandi", "category": "medical_access", "urgency": 4, "pop": 1, "raw": "TB patient in Govandi stopped treatment midway.", "hours_ago": 8, "conf": 0.85, "watch": True},
            {"reporter": reporters[0], "channel": "app",      "zone_id": "Dharavi", "category": "elderly_care",   "urgency": 3, "pop": 1, "raw": "Elderly woman near Dharavi junction needs daily medication and food support.", "hours_ago": 3, "conf": 0.91, "watch": True},
        ]

        # Create needs first
        from app.services.decay import compute_t_score, get_effective_lambda
        from app.services.scoring import compute_all_scores

        need_specs = [
            {"zone": "Zone 6",     "category": "medical_access",   "hours_ago": 4,   "src_count": 3, "urgencies": [5, 5, 4], "reporter_trust": 0.94},
            {"zone": "Zone 4",     "category": "nutrition",         "hours_ago": 12,  "src_count": 3, "urgencies": [4, 4, 3], "reporter_trust": 0.88},
            {"zone": "Kurla East", "category": "shelter",           "hours_ago": 48,  "src_count": 2, "urgencies": [3, 3],    "reporter_trust": 0.79},
            {"zone": "Block 7B",   "category": "water_sanitation",  "hours_ago": 118, "src_count": 2, "urgencies": [2, 2],    "reporter_trust": 0.65},
        ]

        needs = []
        for ns in need_specs:
            last_corroborated = now_utc(ns["hours_ago"])
            t_score = compute_t_score(ns["category"], last_corroborated, ns["reporter_trust"])
            lambda_ph = get_effective_lambda(ns["category"], ns["reporter_trust"])
            c_score = 0.72  # representative corroboration score
            scores = compute_all_scores(
                signal_count=ns["src_count"],
                urgencies=ns["urgencies"],
                need_category=ns["category"],
                c_score=c_score,
                t_score=t_score,
            )
            need = Need(
                zone_id=ns["zone"],
                need_category=ns["category"],
                priority_score=scores.priority_score,
                f_score=scores.f_score, u_score=scores.u_score,
                g_score=scores.g_score, v_score=scores.v_score,
                c_score=c_score, t_score=t_score,
                lambda_per_hour=lambda_ph,
                source_count=ns["src_count"],
                population_est=None,
                status="active",
                first_reported=now_utc(ns["hours_ago"] + 2),
                last_corroborated=last_corroborated,
            )
            db.add(need)
            needs.append(need)
        await db.flush()
        print(f"  ✓ Created {len(needs)} corroborated needs")

        # Create signals and link to needs
        need_mapping = {
            "Zone 6/medical_access": needs[0],
            "Zone 4/nutrition": needs[1],
            "Kurla East/shelter": needs[2],
            "Block 7B/water_sanitation": needs[3],
        }

        signals = []
        for ss in signal_specs:
            key = f"{ss['zone_id']}/{ss['category']}"
            need = need_mapping.get(key)
            is_watch = ss.get("watch", False)
            signal = Signal(
                reporter_id=ss["reporter"].id,
                source_channel=ss["channel"],
                zone_id=ss["zone_id"],
                need_category=ss["category"],
                urgency=ss["urgency"],
                population_est=ss.get("pop"),
                raw_text=ss["raw"],
                confidence=ss["conf"],
                state="watch" if is_watch else "active",
                collected_at=now_utc(ss["hours_ago"]),
                corroboration_id=need.id if need and not is_watch else None,
            )
            db.add(signal)
            signals.append(signal)
        await db.flush()
        print(f"  ✓ Created {len(signals)} signals")

        # ── TASKS ──────────────────────────────────────────────
        # 6 historical tasks: 2 resolved, 2 partial, 2 pending
        task_specs = [
            # Resolved
            {"need": needs[0], "volunteer": volunteers[3], "status": "complete", "dispatched_h": 3, "accepted_h": 2.5, "completed_h": 1, "kinship": False},
            {"need": needs[1], "volunteer": volunteers[0], "status": "complete", "dispatched_h": 10, "accepted_h": 9.5, "completed_h": 6, "kinship": True},
            # Partial
            {"need": needs[2], "volunteer": volunteers[2], "status": "complete", "dispatched_h": 45, "accepted_h": 44, "completed_h": 40, "kinship": False},
            {"need": needs[2], "volunteer": volunteers[1], "status": "complete", "dispatched_h": 44, "accepted_h": 43, "completed_h": 39, "kinship": True},
            # Pending
            {"need": needs[3], "volunteer": volunteers[6], "status": "pending", "dispatched_h": 2, "accepted_h": None, "completed_h": None, "kinship": False},
            {"need": needs[1], "volunteer": volunteers[7], "status": "accepted", "dispatched_h": 5, "accepted_h": 4.5, "completed_h": None, "kinship": False},
        ]

        tasks = []
        for ts in task_specs:
            task = Task(
                need_id=ts["need"].id,
                volunteer_id=ts["volunteer"].id,
                status=ts["status"],
                dispatched_at=now_utc(ts["dispatched_h"]),
                accepted_at=now_utc(ts["accepted_h"]) if ts["accepted_h"] else None,
                completed_at=now_utc(ts["completed_h"]) if ts["completed_h"] else None,
                kinship_bonus=ts["kinship"],
            )
            db.add(task)
            tasks.append(task)
        await db.flush()
        print(f"  ✓ Created {len(tasks)} tasks")

        # ── DEBRIEFS ──────────────────────────────────────────
        debrief_specs = [
            {"task": tasks[0], "volunteer": volunteers[3], "need": needs[0], "resolution": "resolved", "people": 1,  "notes": "Delivered insulin from nearest pharmacy. Patient stabilised."},
            {"task": tasks[1], "volunteer": volunteers[0], "need": needs[1], "resolution": "resolved", "people": 80, "notes": "Distributed ration packages to 80 beneficiaries in Zone 4 with Priya's help."},
            {"task": tasks[2], "volunteer": volunteers[2], "need": needs[2], "resolution": "partial",  "people": 20, "notes": "Found temporary space for 5 families. 10 still displaced, need follow-up."},
        ]
        for ds in debrief_specs:
            debrief = Debrief(
                task_id=ds["task"].id,
                volunteer_id=ds["volunteer"].id,
                need_id=ds["need"].id,
                resolution=ds["resolution"],
                people_helped=ds["people"],
                notes=ds["notes"],
                submitted_at=now_utc(0.5),
            )
            db.add(debrief)
        await db.flush()
        print("  ✓ Created 3 debriefs")

        await db.commit()
        print("\n✅ Database seeded successfully!")
        print(f"   Reporters: {len(reporters)}")
        print(f"   Volunteers: {len(volunteers)}")
        print(f"   Needs: {len(needs)}")
        print(f"   Signals: {len(signals)}")
        print(f"   Tasks: {len(tasks)}")

    # ── FEW-SHOT EXAMPLES JSON ────────────────────────────────
    examples_path = settings.FEW_SHOT_EXAMPLES_PATH
    os.makedirs(os.path.dirname(examples_path) if os.path.dirname(examples_path) else ".", exist_ok=True)

    examples_with_embeddings = []
    for ex in FEW_SHOT_EXAMPLES:
        ex_with_emb = dict(ex)
        ex_with_emb["embedding"] = random_unit_vec(768)  # Pre-computed placeholder
        ex_with_emb["added_at"] = datetime.now(timezone.utc).isoformat()
        examples_with_embeddings.append(ex_with_emb)

    with open(examples_path, "w", encoding="utf-8") as f:
        json.dump({
            "examples": examples_with_embeddings,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "description": "Few-shot examples for Gemini NLP classifier — English + Hindi transliteration",
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✅ few_shot_examples.json written with {len(examples_with_embeddings)} examples")
    print(f"   Path: {examples_path}")
    print("\n🚀 Run 'docker-compose up' to start all services.")


if __name__ == "__main__":
    asyncio.run(seed())
