from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid


# ─── Reporter Schemas ───

class ReporterBase(BaseModel):
    phone: str
    name: Optional[str] = None

class ReporterCreate(ReporterBase):
    pass

class ReporterUpdate(BaseModel):
    trust_score: Optional[float] = None
    name: Optional[str] = None
    justification: Optional[str] = None

class ReporterOut(ReporterBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    trust_score: float
    reports_filed: int
    reports_verified: int
    decay_modifier: float
    created_at: datetime


# ─── Signal Schemas ───

class SignalCreate(BaseModel):
    zone_id: str
    need_category: str
    urgency: Optional[int] = None
    population_est: Optional[int] = None
    raw_text: Optional[str] = None
    source_channel: str = "app"
    reporter_phone: Optional[str] = None
    collected_at: Optional[datetime] = None

class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    reporter_id: Optional[uuid.UUID]
    source_channel: str
    zone_id: str
    need_category: str
    urgency: Optional[int]
    population_est: Optional[int]
    raw_text: Optional[str]
    confidence: Optional[float]
    state: str
    collected_at: datetime
    synced_at: datetime
    corroboration_id: Optional[uuid.UUID]
    classifier: Optional[str] = None


# ─── Need Schemas ───

class NeedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    zone_id: str
    need_category: str
    priority_score: float
    f_score: Optional[float]
    u_score: Optional[float]
    g_score: Optional[float]
    v_score: Optional[float]
    c_score: Optional[float]
    t_score: Optional[float]
    lambda_per_hour: Optional[float]
    source_count: int
    population_est: Optional[int]
    status: str
    first_reported: datetime
    last_corroborated: datetime
    created_at: datetime
    updated_at: datetime

class NeedUpdate(BaseModel):
    g_score: Optional[float] = None
    status: Optional[str] = None

class NeedPromote(BaseModel):
    justification: Optional[str] = None


# ─── Volunteer Schemas ───

class VolunteerCreate(BaseModel):
    phone: str
    name: str
    skills: List[str] = []
    languages: List[str] = []
    has_transport: bool = False
    zone_id: Optional[str] = None
    availability_schedule: Optional[dict] = None
    location_wkt: Optional[str] = None

class VolunteerUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    has_transport: Optional[bool] = None
    zone_id: Optional[str] = None
    is_available: Optional[bool] = None
    availability_schedule: Optional[dict] = None

class VolunteerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    phone: str
    name: str
    skills: List[str]
    languages: List[str]
    has_transport: bool
    zone_id: Optional[str]
    trust_score: float
    completion_rate: float
    is_available: bool
    availability_schedule: Optional[dict]
    created_at: datetime


# ─── Task Schemas ───

class TaskCreate(BaseModel):
    need_id: uuid.UUID
    volunteer_id: uuid.UUID
    kinship_bonus: bool = False

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    need_id: uuid.UUID
    volunteer_id: uuid.UUID
    status: str
    dispatched_at: datetime
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]
    kinship_bonus: bool

class TaskStatusUpdate(BaseModel):
    status: str


# ─── Debrief Schemas ───

class DebriefCreate(BaseModel):
    task_id: uuid.UUID
    volunteer_id: Optional[uuid.UUID] = None  # auto-resolved from task if omitted
    need_id: Optional[uuid.UUID] = None       # auto-resolved from task if omitted
    resolution: str  # resolved | partial | unresolved
    people_helped: Optional[int] = None
    notes: Optional[str] = None

class DebriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    task_id: uuid.UUID
    volunteer_id: uuid.UUID
    need_id: uuid.UUID
    resolution: str
    people_helped: Optional[int]
    notes: Optional[str]
    submitted_at: datetime


# ─── Dispatch Schema ───

class DispatchRequest(BaseModel):
    need_id: uuid.UUID
    volunteer_ids: List[uuid.UUID]
    send_whatsapp: bool = True


# ─── Dashboard Schemas ───

class DashboardStats(BaseModel):
    total_active_needs: int
    total_watch_signals: int
    total_volunteers: int
    available_volunteers: int
    kinship_matches_today: int
    avg_decay_age_days: float
    needs_needing_reverification: int

class HeatmapCell(BaseModel):
    need_category: str
    source_channel: str
    count: int

class SignalLogEntry(BaseModel):
    id: str
    event_type: str
    timestamp: datetime
    description: str
    metadata: dict


# ─── Ingest Schema ───

class IngestRequest(BaseModel):
    zone_id: str
    need_category: Optional[str] = None   # auto-classified from raw_text if omitted
    urgency: Optional[int] = None         # auto-classified from raw_text if omitted
    population_est: Optional[int] = None
    raw_text: Optional[str] = None
    reporter_phone: Optional[str] = None
    source_channel: str = "app"
