"""trainer module columns

Adds what the M2 schema lacks for the Trainer module (M5):
puzzle ownership and lifecycle status, an assignment start date, and a
session learning objective. All changes are additive; existing puzzles
become 'published' library puzzles with no owner.

Revision ID: a5c1e7d2b934
Revises: 29dd76e3604b
Create Date: 2026-11-02 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5c1e7d2b934'
down_revision: Union[str, Sequence[str], None] = '29dd76e3604b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('puzzles', sa.Column('created_by_trainer_id', sa.Uuid(), nullable=True))
    op.add_column('puzzles', sa.Column('status', sa.String(length=20), server_default=sa.text("'published'"), nullable=False))
    op.create_foreign_key(
        op.f('fk_puzzles_created_by_trainer_id_trainer_profiles'),
        'puzzles', 'trainer_profiles',
        ['created_by_trainer_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_check_constraint(
        op.f('ck_puzzles_valid_puzzle_status'),
        'puzzles',
        "status IN ('draft', 'published', 'archived')",
    )
    op.create_index(op.f('ix_puzzles_created_by_trainer_id'), 'puzzles', ['created_by_trainer_id'], unique=False)
    op.create_index(op.f('ix_puzzles_status'), 'puzzles', ['status'], unique=False)

    op.add_column('assignments', sa.Column('start_date', sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(
        op.f('ck_assignments_valid_assignment_dates'),
        'assignments',
        'start_date IS NULL OR due_date IS NULL OR due_date >= start_date',
    )

    op.add_column('class_sessions', sa.Column('learning_objective', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('class_sessions', 'learning_objective')

    op.drop_constraint(op.f('ck_assignments_valid_assignment_dates'), 'assignments', type_='check')
    op.drop_column('assignments', 'start_date')

    op.drop_index(op.f('ix_puzzles_status'), table_name='puzzles')
    op.drop_index(op.f('ix_puzzles_created_by_trainer_id'), table_name='puzzles')
    op.drop_constraint(op.f('ck_puzzles_valid_puzzle_status'), 'puzzles', type_='check')
    op.drop_constraint(op.f('fk_puzzles_created_by_trainer_id_trainer_profiles'), 'puzzles', type_='foreignkey')
    op.drop_column('puzzles', 'status')
    op.drop_column('puzzles', 'created_by_trainer_id')
