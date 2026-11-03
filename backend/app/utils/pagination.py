import math
from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")

MAX_PAGE_SIZE = 100


@dataclass
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


def make_page(items: list, total: int, params: PageParams) -> dict:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "pages": math.ceil(total / params.page_size) if total else 0,
    }


# Alias kept for callers written against the earlier name.
build_page = make_page


def paginate_list(items: list, params: PageParams) -> dict:
    """Paginate a list that had to be filtered in Python."""
    window = items[params.offset : params.offset + params.page_size]
    return make_page(window, len(items), params)


def count_rows(db: Session, query: Select) -> int:
    """Count the rows ``query`` would return, ignoring its ordering."""
    return db.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    ) or 0


def paginate(db: Session, query: Select, params: PageParams) -> tuple[list, int]:
    """Return one page of ``query``'s rows and the total row count."""
    total = count_rows(db, query)
    rows = db.execute(
        query.limit(params.page_size).offset(params.offset)
    ).all()
    return rows, total
