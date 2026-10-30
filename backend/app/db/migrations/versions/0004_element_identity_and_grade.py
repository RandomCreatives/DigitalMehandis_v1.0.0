"""Element identity + concrete grade convention

Adds the three columns that turn ``project_elements`` from a list of drawing
annotations into the spine table the master blueprint calls for:

* ``ext_uid``        stable identity across drawing revisions
* ``revision``       which drawing revision the row was measured from
* ``grade_standard`` which strength convention a concrete grade is quoted in
                     (EBCS_2 = cube, ES_EN_1992_1_1 = cylinder)

Also records the audit trail for BBS laps on ``bbs_bars``: the code of practice
actually applied and the concrete grade it was derived from. Previously the
"EBCS_3" default was written with no record of what was computed or why --
EBCS-3 is Design of Steel Structures, so that default was simply wrong.

Backfill is deterministic (sha1 over project + element code + row id) and runs
in Python so it works on both PostgreSQL and SQLite.

Revision ID: 0004
Revises: 290b7209b478
Create Date: 2026-10-30
"""

import hashlib

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "290b7209b478"
branch_labels = None
depends_on = None


def _backfill_ext_uid(bind) -> None:
    """Give every existing element a stable, reproducible ``ext_uid``.

    The uid is derived from data that does not change (project id, element
    code, row id), so re-running the backfill is idempotent and two
    environments derive the same values.
    """
    rows = bind.execute(
        sa.text(
            "SELECT id, project_id, element_code FROM project_elements "
            "WHERE ext_uid IS NULL"
        )
    ).fetchall()

    for row_id, project_id, element_code in rows:
        seed = f"{project_id}|{element_code or ''}|{row_id}".encode("utf-8")
        ext_uid = hashlib.sha1(seed).hexdigest()  # noqa: S324 - identity, not security
        bind.execute(
            sa.text("UPDATE project_elements SET ext_uid = :uid WHERE id = :id"),
            {"uid": ext_uid, "id": row_id},
        )


def upgrade() -> None:
    # ── project_elements: identity ────────────────────────────────────────────
    with op.batch_alter_table("project_elements") as batch_op:
        batch_op.add_column(sa.Column("ext_uid", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("revision", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("grade_standard", sa.String(40), nullable=True))

    _backfill_ext_uid(op.get_bind())

    # The uniqueness guarantee is per (project, element, revision). Rows that
    # predate revisions get a placeholder instead of NULL, because SQL treats
    # NULLs as distinct and would otherwise let duplicate uids through.
    op.execute("UPDATE project_elements SET revision = 'R0' WHERE revision IS NULL")

    op.create_index(
        "ix_project_elements_ext_uid", "project_elements", ["ext_uid"], unique=False
    )
    op.create_index(
        "uq_project_element_uid_revision",
        "project_elements",
        ["project_id", "ext_uid", "revision"],
        unique=True,
    )

    # ── bbs_bars: audit trail for the lap calculation ─────────────────────────
    with op.batch_alter_table("bbs_bars") as batch_op:
        batch_op.add_column(sa.Column("design_code", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("concrete_grade", sa.String(20), nullable=True))

    # Legacy rows were computed with the old hard-coded 50*phi rule. Label them
    # as what they actually are instead of claiming a code they never followed.
    op.execute(
        "UPDATE bbs_bars SET design_code = 'EBCS_2_LEGACY_50D' "
        "WHERE design_code IS NULL AND lap_length_mm IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("bbs_bars") as batch_op:
        batch_op.drop_column("concrete_grade")
        batch_op.drop_column("design_code")

    op.drop_index("uq_project_element_uid_revision", table_name="project_elements")
    op.drop_index("ix_project_elements_ext_uid", table_name="project_elements")

    with op.batch_alter_table("project_elements") as batch_op:
        batch_op.drop_column("grade_standard")
        batch_op.drop_column("revision")
        batch_op.drop_column("ext_uid")
