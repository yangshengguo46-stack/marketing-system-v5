"""Independent SQL metadata for the fifth-version incubation truth ledger."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import AsyncEngine

CURRENT_INCUBATION_SCHEMA_VERSION = 2
INCUBATION_SCHEMA_COMPONENT = "mcn-incubation-core"
INCUBATION_BOOTSTRAP_LOCK_KEY = 0x24E71CBA5A120002


class UnsupportedIncubationSchemaVersion(RuntimeError):
    """The database contains an unsupported incubation schema version."""


class IncubationSchemaNotInitialized(RuntimeError):
    """The incubation schema version row is missing."""


incubation_metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)

incubation_schema_versions = Table(
    "incubation_schema_versions",
    incubation_metadata,
    Column("component", String(64), primary_key=True),
    Column("version", Integer, nullable=False),
    Column("applied_at", DateTime(timezone=True), nullable=False),
)

incubation_projects = Table(
    "incubation_projects",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("project_id", String(255), primary_key=True),
    Column("subject_kind", String(64), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
)

incubation_operation_receipts = Table(
    "incubation_operation_receipts",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("operation_key", String(255), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("result_kind", String(64), nullable=False),
    Column("result_id", String(255), nullable=False),
    Column("result_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

incubation_project_truths = Table(
    "incubation_project_truths",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("truth_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("kind", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_evidence_items = Table(
    "incubation_evidence_items",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("evidence_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("kind", String(64), nullable=False),
    Column("status", String(64), nullable=False),
    Column("captured_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_brief_versions = Table(
    "incubation_brief_versions",
    incubation_metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", String(255), nullable=False),
    Column("brief_version_id", String(255), nullable=False),
    Column("brief_id", String(255), nullable=False),
    Column("version", Integer, nullable=False),
    Column("project_id", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("owner_id", "brief_version_id"),
    UniqueConstraint("owner_id", "project_id", "brief_id", "version"),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_decision_versions = Table(
    "incubation_decision_versions",
    incubation_metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", String(255), nullable=False),
    Column("decision_version_id", String(255), nullable=False),
    Column("decision_id", String(255), nullable=False),
    Column("version", Integer, nullable=False),
    Column("project_id", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("owner_id", "decision_version_id"),
    UniqueConstraint("owner_id", "project_id", "decision_id", "version"),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_experiments = Table(
    "incubation_experiments",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("experiment_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("decision_version_id", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_outcome_observations = Table(
    "incubation_outcome_observations",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("observation_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("experiment_id", String(255), nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_learning_decisions = Table(
    "incubation_learning_decisions",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("learning_decision_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("experiment_id", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)

incubation_case_episodes = Table(
    "incubation_case_episodes",
    incubation_metadata,
    Column("owner_id", String(255), primary_key=True),
    Column("case_episode_id", String(255), primary_key=True),
    Column("project_id", String(255), nullable=False),
    Column("status", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSON, nullable=False),
    ForeignKeyConstraint(
        ["owner_id", "project_id"],
        ["incubation_projects.owner_id", "incubation_projects.project_id"],
    ),
)


async def bootstrap_incubation_schema(engine: AsyncEngine) -> None:
    """Create the new ledger without reading or changing any legacy metadata."""

    async with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(:lock_key)"),
                {"lock_key": INCUBATION_BOOTSTRAP_LOCK_KEY},
            )
        await connection.run_sync(
            lambda sync_connection: incubation_schema_versions.create(
                sync_connection,
                checkfirst=True,
            )
        )
        version = await connection.scalar(select(incubation_schema_versions.c.version).where(incubation_schema_versions.c.component == INCUBATION_SCHEMA_COMPONENT))
        if version is not None and version not in {1, CURRENT_INCUBATION_SCHEMA_VERSION}:
            raise UnsupportedIncubationSchemaVersion(f"database schema version is {version}; runtime expects {CURRENT_INCUBATION_SCHEMA_VERSION}")
        await connection.run_sync(incubation_metadata.create_all)
        if version is None:
            await connection.execute(
                insert(incubation_schema_versions).values(
                    component=INCUBATION_SCHEMA_COMPONENT,
                    version=CURRENT_INCUBATION_SCHEMA_VERSION,
                    applied_at=datetime.now(UTC),
                )
            )
        elif version == 1:
            await connection.execute(
                update(incubation_schema_versions)
                .where(
                    incubation_schema_versions.c.component == INCUBATION_SCHEMA_COMPONENT,
                    incubation_schema_versions.c.version == 1,
                )
                .values(
                    version=CURRENT_INCUBATION_SCHEMA_VERSION,
                    applied_at=datetime.now(UTC),
                )
            )


async def read_incubation_schema_version(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        version = await connection.scalar(select(incubation_schema_versions.c.version).where(incubation_schema_versions.c.component == INCUBATION_SCHEMA_COMPONENT))
    if version is None:
        raise IncubationSchemaNotInitialized("incubation schema version is missing")
    return int(version)


__all__ = [
    "CURRENT_INCUBATION_SCHEMA_VERSION",
    "bootstrap_incubation_schema",
    "incubation_evidence_items",
    "incubation_metadata",
    "read_incubation_schema_version",
]
