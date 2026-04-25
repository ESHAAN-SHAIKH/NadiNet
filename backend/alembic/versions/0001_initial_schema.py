"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    # reporters
    op.create_table(
        'reporters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('phone', sa.Text(), unique=True, nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='0.65'),
        sa.Column('reports_filed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reports_verified', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('decay_modifier', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # needs
    op.create_table(
        'needs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('zone_id', sa.Text(), nullable=False),
        sa.Column('need_category', sa.Text(), nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('f_score', sa.Float(), nullable=True),
        sa.Column('u_score', sa.Float(), nullable=True),
        sa.Column('g_score', sa.Float(), nullable=True),
        sa.Column('v_score', sa.Float(), nullable=True),
        sa.Column('c_score', sa.Float(), nullable=True),
        sa.Column('t_score', sa.Float(), nullable=True),
        sa.Column('lambda_per_hour', sa.Float(), nullable=True),
        sa.Column('source_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('population_est', sa.Integer(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False, server_default="'active'"),
        sa.Column('first_reported', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_corroborated', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('location_wkt', sa.Text(), nullable=True),
    )
    # Add PostGIS geography column to needs
    op.execute("ALTER TABLE needs ADD COLUMN IF NOT EXISTS location GEOGRAPHY(POINT, 4326)")

    # signals
    op.create_table(
        'signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('reporters.id'), nullable=True),
        sa.Column('source_channel', sa.Text(), nullable=False),
        sa.Column('zone_id', sa.Text(), nullable=False),
        sa.Column('need_category', sa.Text(), nullable=False),
        sa.Column('urgency', sa.Integer(), nullable=True),
        sa.Column('population_est', sa.Integer(), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('state', sa.Text(), nullable=False, server_default="'watch'"),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('corroboration_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('needs.id'), nullable=True),
        sa.Column('manually_confirmed', sa.Boolean(), server_default='false'),
    )

    # volunteers
    op.create_table(
        'volunteers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('phone', sa.Text(), unique=True, nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('skills', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('languages', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('has_transport', sa.Boolean(), server_default='false'),
        sa.Column('zone_id', sa.Text(), nullable=True),
        sa.Column('trust_score', sa.Float(), nullable=False, server_default='0.65'),
        sa.Column('completion_rate', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('availability_schedule', postgresql.JSONB(), nullable=True),
        sa.Column('location_wkt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    # Add PostGIS geography column to volunteers
    op.execute("ALTER TABLE volunteers ADD COLUMN IF NOT EXISTS location GEOGRAPHY(POINT, 4326)")

    # kinship_edges
    op.create_table(
        'kinship_edges',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('volunteer_a_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('volunteers.id'), nullable=False),
        sa.Column('volunteer_b_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('volunteers.id'), nullable=False),
        sa.Column('co_deployments', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('quality_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('last_deployed', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('volunteer_a_id', 'volunteer_b_id', name='uq_kinship_pair'),
    )

    # tasks
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('need_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('needs.id'), nullable=False),
        sa.Column('volunteer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('volunteers.id'), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default="'pending'"),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kinship_bonus', sa.Boolean(), server_default='false'),
    )

    # debriefs
    op.create_table(
        'debriefs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id'), nullable=False),
        sa.Column('volunteer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('volunteers.id'), nullable=False),
        sa.Column('need_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('needs.id'), nullable=False),
        sa.Column('resolution', sa.Text(), nullable=False),
        sa.Column('people_helped', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    # conversations
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('phone', sa.Text(), unique=True, nullable=False),
        sa.Column('state', sa.Text(), nullable=False, server_default="'IDLE'"),
        sa.Column('context', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('conversations')
    op.drop_table('debriefs')
    op.drop_table('tasks')
    op.drop_table('kinship_edges')
    op.drop_table('volunteers')
    op.drop_table('signals')
    op.drop_table('needs')
    op.drop_table('reporters')
