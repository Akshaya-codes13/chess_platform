
"""m5_m12 features

Additive schema for milestones M5-M12:

- puzzle_attempts: the moves the student played and the hints they used (M6);
- game_databases / game_folders / pgn_games: the PGN game library (M9);
- daily_platform_summaries / daily_trainer_summaries: precomputed report
  rows written by the ARQ daily summary job (M11);
- media_files: uploaded images kept in object storage (M12);
- posts.published_at and a post status check (M12);
- feedback: audience (trainer or admin team), rating, review status and
  response. to_user_id becomes optional for admin-team feedback (M12);
- two assignment-completion badges (M10). Downgrade keeps them, because
  students may already have earned them.

Nothing is dropped and no existing row changes meaning: existing feedback
rows get audience 'trainer' and status 'open'.

Revision ID: 6da2d4bece7b
Revises: a5c1e7d2b934
Create Date: 2026-11-03 16:51:21.825109

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6da2d4bece7b'
down_revision: Union[str, Sequence[str], None] = 'a5c1e7d2b934'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('daily_platform_summaries',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('summary_date', sa.Date(), nullable=False),
    sa.Column('new_students', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('new_trainers', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('active_students', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('sessions_held', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_present', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_late', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_absent', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_excused', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('submissions', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('puzzle_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('puzzles_solved', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('xp_awarded', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_daily_platform_summaries')),
    sa.UniqueConstraint('summary_date', name=op.f('uq_daily_platform_summaries_summary_date'))
    )
    op.create_table('game_databases',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('is_shared', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_game_databases_owner_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_game_databases'))
    )
    op.create_index(op.f('ix_game_databases_owner_id'), 'game_databases', ['owner_id'], unique=False)
    op.create_table('media_files',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('uploaded_by', sa.Uuid(), nullable=False),
    sa.Column('storage_key', sa.String(length=255), nullable=False),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_media_files_uploaded_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_media_files')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_media_files_storage_key'))
    )
    op.create_index(op.f('ix_media_files_uploaded_by'), 'media_files', ['uploaded_by'], unique=False)
    op.create_table('daily_trainer_summaries',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('trainer_id', sa.Uuid(), nullable=False),
    sa.Column('summary_date', sa.Date(), nullable=False),
    sa.Column('sessions_held', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_present', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_late', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_absent', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('attendance_excused', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('submissions', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('active_students', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('puzzle_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('puzzles_solved', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['trainer_id'], ['trainer_profiles.id'], name=op.f('fk_daily_trainer_summaries_trainer_id_trainer_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_daily_trainer_summaries')),
    sa.UniqueConstraint('trainer_id', 'summary_date', name='unique_trainer_summary_date')
    )
    op.create_index(op.f('ix_daily_trainer_summaries_summary_date'), 'daily_trainer_summaries', ['summary_date'], unique=False)
    op.create_index(op.f('ix_daily_trainer_summaries_trainer_id'), 'daily_trainer_summaries', ['trainer_id'], unique=False)
    op.create_table('game_folders',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('database_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['database_id'], ['game_databases.id'], name=op.f('fk_game_folders_database_id_game_databases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_id'], ['game_folders.id'], name=op.f('fk_game_folders_parent_id_game_folders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_game_folders'))
    )
    op.create_index(op.f('ix_game_folders_database_id'), 'game_folders', ['database_id'], unique=False)
    op.create_index(op.f('ix_game_folders_parent_id'), 'game_folders', ['parent_id'], unique=False)
    op.create_table('pgn_games',
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('database_id', sa.Uuid(), nullable=False),
    sa.Column('folder_id', sa.Uuid(), nullable=True),
    sa.Column('uploaded_by', sa.Uuid(), nullable=False),
    sa.Column('white', sa.String(length=150), nullable=False),
    sa.Column('black', sa.String(length=150), nullable=False),
    sa.Column('result', sa.String(length=10), nullable=False),
    sa.Column('event', sa.String(length=200), nullable=True),
    sa.Column('site', sa.String(length=200), nullable=True),
    sa.Column('game_date', sa.String(length=20), nullable=True),
    sa.Column('round', sa.String(length=20), nullable=True),
    sa.Column('eco', sa.String(length=10), nullable=True),
    sa.Column('white_elo', sa.Integer(), nullable=True),
    sa.Column('black_elo', sa.Integer(), nullable=True),
    sa.Column('initial_fen', sa.String(length=200), nullable=True),
    sa.Column('moves', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('ply_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('headers', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('pgn', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("result IN ('1-0', '0-1', '1/2-1/2', '*')", name=op.f('ck_pgn_games_valid_pgn_result')),
    sa.CheckConstraint('ply_count >= 0', name=op.f('ck_pgn_games_non_negative_ply_count')),
    sa.ForeignKeyConstraint(['database_id'], ['game_databases.id'], name=op.f('fk_pgn_games_database_id_game_databases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['folder_id'], ['game_folders.id'], name=op.f('fk_pgn_games_folder_id_game_folders'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_pgn_games_uploaded_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pgn_games'))
    )
    op.create_index(op.f('ix_pgn_games_database_id'), 'pgn_games', ['database_id'], unique=False)
    op.create_index(op.f('ix_pgn_games_folder_id'), 'pgn_games', ['folder_id'], unique=False)
    op.create_index(op.f('ix_pgn_games_uploaded_by'), 'pgn_games', ['uploaded_by'], unique=False)
    op.add_column('feedback', sa.Column('audience', sa.String(length=20), server_default=sa.text("'trainer'"), nullable=False))
    op.add_column('feedback', sa.Column('rating', sa.Integer(), nullable=True))
    op.add_column('feedback', sa.Column('status', sa.String(length=20), server_default=sa.text("'open'"), nullable=False))
    op.add_column('feedback', sa.Column('response', sa.Text(), nullable=True))
    op.add_column('feedback', sa.Column('reviewed_by', sa.Uuid(), nullable=True))
    op.add_column('feedback', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('feedback', 'to_user_id',
               existing_type=sa.UUID(),
               nullable=True)
    op.create_index(op.f('ix_feedback_audience'), 'feedback', ['audience'], unique=False)
    op.create_index(op.f('ix_feedback_status'), 'feedback', ['status'], unique=False)
    op.create_foreign_key(op.f('fk_feedback_reviewed_by_users'), 'feedback', 'users', ['reviewed_by'], ['id'], ondelete='RESTRICT')
    op.create_check_constraint(op.f('ck_feedback_valid_feedback_audience'), 'feedback', "audience IN ('trainer', 'admin')")
    op.create_check_constraint(op.f('ck_feedback_trainer_feedback_has_recipient'), 'feedback', "audience = 'admin' OR to_user_id IS NOT NULL")
    op.create_check_constraint(op.f('ck_feedback_valid_feedback_status'), 'feedback', "status IN ('open', 'reviewed')")
    op.create_check_constraint(op.f('ck_feedback_valid_feedback_rating'), 'feedback', 'rating IS NULL OR (rating >= 1 AND rating <= 5)')
    op.add_column('posts', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_posts_published_at'), 'posts', ['published_at'], unique=False)
    op.create_check_constraint(op.f('ck_posts_valid_post_status'), 'posts', "status IN ('draft', 'published', 'archived')")
    op.add_column('puzzle_attempts', sa.Column('moves', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column('puzzle_attempts', sa.Column('hints_used', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.create_check_constraint(op.f('ck_puzzle_attempts_non_negative_hints_used'), 'puzzle_attempts', 'hints_used >= 0')

    # Badges for completing assignments (M10). Existing rows are left alone.
    op.execute(
        """
        INSERT INTO badges (code, name, description, xp_reward) VALUES
            ('first-assignment-completed', 'Homework Hero', 'Complete your first assignment.', 15),
            ('five-assignments-completed', 'Consistent Learner', 'Complete five assignments.', 40)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Restoring NOT NULL on feedback.to_user_id would need admin-team feedback
    # to be deleted. Refuse instead of dropping data.
    bind = op.get_bind()
    orphaned = bind.execute(sa.text("SELECT count(*) FROM feedback WHERE to_user_id IS NULL")).scalar()
    if orphaned:
        raise RuntimeError(
            f"{orphaned} admin-team feedback rows have no single recipient; "
            "export or reassign them before downgrading."
        )

    op.drop_constraint(op.f('ck_puzzle_attempts_non_negative_hints_used'), 'puzzle_attempts', type_='check')
    op.drop_constraint(op.f('ck_posts_valid_post_status'), 'posts', type_='check')
    op.drop_constraint(op.f('ck_feedback_valid_feedback_rating'), 'feedback', type_='check')
    op.drop_constraint(op.f('ck_feedback_valid_feedback_status'), 'feedback', type_='check')
    op.drop_constraint(op.f('ck_feedback_trainer_feedback_has_recipient'), 'feedback', type_='check')
    op.drop_constraint(op.f('ck_feedback_valid_feedback_audience'), 'feedback', type_='check')
    op.drop_column('puzzle_attempts', 'hints_used')
    op.drop_column('puzzle_attempts', 'moves')
    op.drop_index(op.f('ix_posts_published_at'), table_name='posts')
    op.drop_column('posts', 'published_at')
    op.drop_constraint(op.f('fk_feedback_reviewed_by_users'), 'feedback', type_='foreignkey')
    op.drop_index(op.f('ix_feedback_status'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_audience'), table_name='feedback')
    op.alter_column('feedback', 'to_user_id',
               existing_type=sa.UUID(),
               nullable=False)
    op.drop_column('feedback', 'reviewed_at')
    op.drop_column('feedback', 'reviewed_by')
    op.drop_column('feedback', 'response')
    op.drop_column('feedback', 'status')
    op.drop_column('feedback', 'rating')
    op.drop_column('feedback', 'audience')
    op.drop_index(op.f('ix_pgn_games_uploaded_by'), table_name='pgn_games')
    op.drop_index(op.f('ix_pgn_games_folder_id'), table_name='pgn_games')
    op.drop_index(op.f('ix_pgn_games_database_id'), table_name='pgn_games')
    op.drop_table('pgn_games')
    op.drop_index(op.f('ix_game_folders_parent_id'), table_name='game_folders')
    op.drop_index(op.f('ix_game_folders_database_id'), table_name='game_folders')
    op.drop_table('game_folders')
    op.drop_index(op.f('ix_daily_trainer_summaries_trainer_id'), table_name='daily_trainer_summaries')
    op.drop_index(op.f('ix_daily_trainer_summaries_summary_date'), table_name='daily_trainer_summaries')
    op.drop_table('daily_trainer_summaries')
    op.drop_index(op.f('ix_media_files_uploaded_by'), table_name='media_files')
    op.drop_table('media_files')
    op.drop_index(op.f('ix_game_databases_owner_id'), table_name='game_databases')
    op.drop_table('game_databases')
    op.drop_table('daily_platform_summaries')
