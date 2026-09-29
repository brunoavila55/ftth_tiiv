import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_permission, validate_csrf
from app.db.session import get_db
from app.modules.inventory import wireless_service
from app.schemas.common import PaginatedResponse, PaginationParams, UuidStr
from app.schemas.wireless import RadioLinkCreate, RadioLinkRead, RadioLinkUpdate

wireless_router = APIRouter(prefix="/radio-links", tags=["Wireless"])


@wireless_router.get(
    "",
    response_model=PaginatedResponse[RadioLinkRead],
    dependencies=[Depends(require_permission("network:read"))],
)
def list_radio_links(
    pagination: PaginationParams = Depends(),
    site_id: UuidStr | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> PaginatedResponse[RadioLinkRead]:
    links, total = wireless_service.list_radio_links(
        db,
        page=pagination.page,
        page_size=pagination.page_size,
        site_id=uuid.UUID(site_id) if site_id else None,
        q=q,
    )
    return PaginatedResponse[RadioLinkRead](
        items=[wireless_service.radio_link_to_read(link) for link in links],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@wireless_router.post(
    "",
    response_model=RadioLinkRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def create_radio_link(
    payload: RadioLinkCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> RadioLinkRead:
    link = wireless_service.create_radio_link(db, payload)
    response.headers["ETag"] = f'"{link.version}"'
    return wireless_service.radio_link_to_read(link)


@wireless_router.get(
    "/{link_id}",
    response_model=RadioLinkRead,
    dependencies=[Depends(require_permission("network:read"))],
)
def get_radio_link(
    link_id: UuidStr,
    response: Response,
    db: Session = Depends(get_db),
) -> RadioLinkRead:
    link = wireless_service.get_radio_link(db, uuid.UUID(link_id))
    response.headers["ETag"] = f'"{link.version}"'
    return wireless_service.radio_link_to_read(link)


@wireless_router.patch(
    "/{link_id}",
    response_model=RadioLinkRead,
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def update_radio_link(
    link_id: UuidStr,
    payload: RadioLinkUpdate,
    response: Response,
    if_match: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> RadioLinkRead:
    link = wireless_service.update_radio_link(db, uuid.UUID(link_id), payload, if_match)
    response.headers["ETag"] = f'"{link.version}"'
    return wireless_service.radio_link_to_read(link)


@wireless_router.delete(
    "/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_permission("network:write")), Depends(validate_csrf)],
)
def delete_radio_link(
    link_id: UuidStr,
    if_match: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    wireless_service.delete_radio_link(db, uuid.UUID(link_id), if_match)
