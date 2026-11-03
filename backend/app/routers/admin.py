import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models import User
from app.schemas.admin import (
    ActivityItem,
    AdminUserCreate,
    AdminUserDetail,
    AdminUserSummary,
    AdminUserUpdate,
    AssignmentOverviewItem,
    DashboardResponse,
    GroupCreate,
    GroupDetail,
    GroupStudentsAdd,
    GroupSummary,
    GroupTrainerAssign,
    GroupUpdate,
    PuzzleDetail,
    PuzzleFilterOptions,
    PuzzleSummary,
    ReportsOverview,
    Role,
    RoleChangeRequest,
    SessionOverviewItem,
    StatusChangeRequest,
    StudentCreate,
    StudentLevel,
    StudentListItem,
    TrainerCreate,
    TrainerListItem,
)
from app.services import admin_reports_service as reports
from app.services import admin_service
from app.services.admin_service import AdminContext
from app.utils.pagination import Page, PageParams, page_params

# Every route requires the admin role: no token or an invalid one gives 401,
# trainers and students get 403.
router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)

SearchQuery = Query(None, max_length=100)


def admin_context(
    request: Request,
    admin: User = Depends(require_admin),
) -> AdminContext:
    return AdminContext(
        actor=admin,
        ip_address=request.client.host if request.client else None,
    )


# Dashboard, activity and reports


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    return reports.get_dashboard(db)


@router.get("/activity", response_model=Page[ActivityItem])
def list_activity(
    entity_type: str | None = Query(None, max_length=100),
    action: str | None = Query(None, max_length=100),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return reports.list_activity(db, params, entity_type=entity_type, action=action)


@router.get("/reports/overview", response_model=ReportsOverview)
def get_reports_overview(db: Session = Depends(get_db)):
    return reports.get_reports_overview(db)


# Users


@router.get("/users", response_model=Page[AdminUserSummary])
def list_users(
    search: str | None = SearchQuery,
    role: Role | None = None,
    is_active: bool | None = None,
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return admin_service.list_users(db, params, search=search, role=role, is_active=is_active)


@router.post("/users", response_model=AdminUserDetail, status_code=status.HTTP_201_CREATED)
def create_user(
    data: AdminUserCreate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.create_account(
        db, ctx,
        role=data.role,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        phone=data.phone,
        trainer_profile=data.trainer_profile.model_dump() if data.trainer_profile else None,
        student_profile=data.student_profile.model_dump() if data.student_profile else None,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin_service.get_user_detail(db, user_id)


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
def update_user(
    user_id: uuid.UUID,
    data: AdminUserUpdate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.update_user(db, ctx, user_id, data.model_dump(exclude_unset=True))


@router.patch("/users/{user_id}/role", response_model=AdminUserDetail)
def change_role(
    user_id: uuid.UUID,
    data: RoleChangeRequest,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.change_role(db, ctx, user_id, data.role, data.trainer_user_id)


@router.patch("/users/{user_id}/status", response_model=AdminUserDetail)
def change_status(
    user_id: uuid.UUID,
    data: StatusChangeRequest,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.change_status(db, ctx, user_id, data.is_active)


# Trainers and students (IDs are user IDs)


@router.get("/trainers", response_model=Page[TrainerListItem])
def list_trainers(
    search: str | None = SearchQuery,
    is_active: bool | None = None,
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return admin_service.list_trainers(db, params, search=search, is_active=is_active)


@router.post("/trainers", response_model=AdminUserDetail, status_code=status.HTTP_201_CREATED)
def create_trainer(
    data: TrainerCreate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.create_account(
        db, ctx,
        role="trainer",
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        phone=data.phone,
        trainer_profile=data.profile.model_dump(),
    )


@router.get("/trainers/{trainer_id}", response_model=AdminUserDetail)
def get_trainer(trainer_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin_service.get_user_detail(db, trainer_id, role="trainer")


@router.get("/students", response_model=Page[StudentListItem])
def list_students(
    search: str | None = SearchQuery,
    is_active: bool | None = None,
    level: StudentLevel | None = None,
    trainer_id: uuid.UUID | None = Query(None, description="Primary trainer's user ID."),
    group_id: uuid.UUID | None = None,
    exclude_group_id: uuid.UUID | None = Query(
        None, description="Only students who are not members of this group."
    ),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return admin_service.list_students(
        db, params,
        search=search,
        is_active=is_active,
        level=level,
        trainer_user_id=trainer_id,
        group_id=group_id,
        exclude_group_id=exclude_group_id,
    )


@router.post("/students", response_model=AdminUserDetail, status_code=status.HTTP_201_CREATED)
def create_student(
    data: StudentCreate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.create_account(
        db, ctx,
        role="student",
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        phone=data.phone,
        student_profile=data.profile.model_dump(),
    )


@router.get("/students/{student_id}", response_model=AdminUserDetail)
def get_student(student_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin_service.get_user_detail(db, student_id, role="student")


# Groups


@router.get("/groups", response_model=Page[GroupSummary])
def list_groups(
    search: str | None = SearchQuery,
    is_active: bool | None = None,
    trainer_id: uuid.UUID | None = Query(None, description="Trainer's user ID."),
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return admin_service.list_groups(
        db, params, search=search, is_active=is_active, trainer_user_id=trainer_id
    )


@router.post("/groups", response_model=GroupDetail, status_code=status.HTTP_201_CREATED)
def create_group(
    data: GroupCreate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.create_group(db, ctx, data.model_dump())


@router.get("/groups/{group_id}", response_model=GroupDetail)
def get_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    return admin_service.get_group_detail(db, group_id)


@router.patch("/groups/{group_id}", response_model=GroupDetail)
def update_group(
    group_id: uuid.UUID,
    data: GroupUpdate,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.update_group(db, ctx, group_id, data.model_dump(exclude_unset=True))


@router.put("/groups/{group_id}/trainer", response_model=GroupDetail)
def assign_trainer(
    group_id: uuid.UUID,
    data: GroupTrainerAssign,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.assign_trainer(db, ctx, group_id, data.trainer_user_id)


@router.post("/groups/{group_id}/students", response_model=GroupDetail)
def add_group_students(
    group_id: uuid.UUID,
    data: GroupStudentsAdd,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return admin_service.add_students(db, ctx, group_id, data.student_user_ids)


@router.delete(
    "/groups/{group_id}/students/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_group_student(
    group_id: uuid.UUID,
    student_id: uuid.UUID,
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    admin_service.remove_student(db, ctx, group_id, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Puzzles


@router.get("/puzzles/filters", response_model=PuzzleFilterOptions)
def get_puzzle_filters(db: Session = Depends(get_db)):
    return reports.puzzle_filter_options(db)


@router.get("/puzzles", response_model=Page[PuzzleSummary])
def list_puzzles(
    search: str | None = SearchQuery,
    status_filter: Literal["draft", "published", "archived"] | None = Query(None, alias="status"),
    category_id: uuid.UUID | None = None,
    theme_id: uuid.UUID | None = None,
    type: str | None = Query(None, max_length=20),
    source: str | None = Query(None, max_length=50),
    min_rating: int | None = Query(None, ge=0),
    max_rating: int | None = Query(None, ge=0),
    incomplete_only: bool = False,
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return reports.list_puzzles(
        db, params,
        search=search,
        status=status_filter,
        category_id=category_id,
        theme_id=theme_id,
        puzzle_type=type,
        source=source,
        min_rating=min_rating,
        max_rating=max_rating,
        incomplete_only=incomplete_only,
    )


@router.get("/puzzles/{puzzle_id}", response_model=PuzzleDetail)
def get_puzzle(puzzle_id: uuid.UUID, db: Session = Depends(get_db)):
    return reports.get_puzzle_detail(db, puzzle_id)


@router.post("/puzzles/{puzzle_id}/{action}", response_model=PuzzleDetail)
def change_puzzle_status(
    puzzle_id: uuid.UUID,
    action: Literal["publish", "archive"],
    ctx: AdminContext = Depends(admin_context),
    db: Session = Depends(get_db),
):
    return reports.change_puzzle_status(db, ctx, puzzle_id, action)


# Assignments and sessions (read-only oversight)


@router.get("/assignments", response_model=Page[AssignmentOverviewItem])
def list_assignments(
    search: str | None = SearchQuery,
    status_filter: Literal["draft", "published", "completed", "cancelled"] | None = Query(
        None, alias="status"
    ),
    trainer_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return reports.list_assignments(
        db, params,
        search=search,
        status=status_filter,
        trainer_user_id=trainer_id,
        group_id=group_id,
    )


@router.get("/sessions", response_model=Page[SessionOverviewItem])
def list_sessions(
    status_filter: Literal["scheduled", "ongoing", "completed", "cancelled"] | None = Query(
        None, alias="status"
    ),
    timeframe: Literal["upcoming", "past"] | None = None,
    trainer_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
    params: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    return reports.list_sessions(
        db, params,
        status=status_filter,
        timeframe=timeframe,
        trainer_user_id=trainer_id,
        group_id=group_id,
    )
