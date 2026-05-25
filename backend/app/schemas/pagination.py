"""Pagination envelope for list endpoints.

Shape (matches REVIEW_API_CONTRACT.md §1 row 1 — `{items, total, limit, offset}`):

    {
        "items":  list[T],        # the rows for this page (already sliced)
        "total":  int | None,     # full count when cheap; null when not computed
        "limit":  int,            # echoed back so the client knows the page size
        "offset": int,            # echoed back so the client can paginate forward
    }

Frontend breaking-change runway: every list endpoint that used to return a
bare array now returns this envelope. Day-2 we can backfill `total` for
endpoints that initially ship `total=null` without breaking consumers.

The class is `Generic[T]` so a route declaring
`response_model=PaginatedResponse[ProjectResponse]` gets a real OpenAPI
schema with the row type inlined — generated SDK clients see typed lists
instead of `any`.
"""

from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard envelope returned by every list endpoint.

    Use `paginate()` below if you have an in-memory list and just need to
    slice it; for DB-paginated queries set `total` explicitly to a cheap
    COUNT(*) (or `None` if the count would be expensive).
    """

    # `model_config` is set so OpenAPI generators see a stable schema name
    # per concrete instantiation (PaginatedResponse[ProjectResponse], etc.).
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: List[T] = Field(default_factory=list, description="Rows on this page.")
    total: Optional[int] = Field(
        default=None,
        description="Full row count across all pages. May be null when computing it is too expensive.",
    )
    limit: int = Field(default=50, ge=0, description="Page size the server applied.")
    offset: int = Field(default=0, ge=0, description="Row index where this page starts (0-based).")


def paginate(rows: List[T], *, limit: int, offset: int, total: Optional[int] = None) -> PaginatedResponse[T]:
    """Slice an in-memory list into a `PaginatedResponse` envelope.

    `total` defaults to the unsliced row count when not supplied — accurate
    when `rows` already represents the full result set, misleading otherwise.
    Pass `total` explicitly for DB-paginated callers where `rows` is just
    the current page.
    """
    if total is None:
        total = len(rows)
    page = rows[offset : offset + limit] if (limit or offset) else list(rows)
    return PaginatedResponse[T](items=page, total=total, limit=limit, offset=offset)
