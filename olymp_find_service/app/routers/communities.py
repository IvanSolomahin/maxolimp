from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Club, CommunitySource, OnlineCommunity

router = APIRouter(prefix="/communities", tags=["communities"])
Db = Annotated[AsyncSession, Depends(get_db)]
SUBJECTS = {"Физика", "Математика"}


class ClubWrite(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    address: str = Field(min_length=1, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    subject: str
    status: str | None = None
    note: str | None = None
    source: str | None = None


class OnlineCommunityWrite(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    subject: str = Field(min_length=1, max_length=100)
    platform: str = Field(min_length=1, max_length=80)
    url: HttpUrl
    description: str | None = None
    sort_order: int = 0


def club_item(club: Club, distance: float | None = None) -> dict:
    return {
        "id": club.id, "name": club.name, "address": club.address,
        "latitude": float(club.latitude) if club.latitude is not None else None,
        "longitude": float(club.longitude) if club.longitude is not None else None,
        "subject": club.subject, "status": club.status, "note": club.note,
        "source": club.source, "distance_km": round(distance, 1) if distance is not None else None,
    }


def online_item(chat: OnlineCommunity) -> dict:
    return {"id": chat.id, "name": chat.name, "subject": chat.subject,
            "platform": chat.platform, "url": chat.url, "description": chat.description,
            "sort_order": chat.sort_order}


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 6371 * 2 * asin(sqrt(a))


@router.get("/options")
async def community_options(db: Db):
    subjects = [subject for subject in (await db.execute(
        select(Club.subject).where(Club.subject.is_not(None)).distinct().order_by(Club.subject)
    )).scalars() if subject in SUBJECTS]
    return {"cities": ["Санкт-Петербург"], "subjects": subjects or sorted(SUBJECTS)}


@router.get("/clubs")
async def search_clubs(
    db: Db,
    subject: str | None = None,
    city: str = Query("Санкт-Петербург", min_length=1),
    q: str | None = None,
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    radius_km: float | None = Query(None, gt=0, le=500),
):
    if subject and subject not in SUBJECTS:
        raise HTTPException(400, "В тестовом режиме доступны математика и физика")
    if city.strip().casefold() not in {"санкт-петербург", "петербург", "спб", "saint petersburg"}:
        return {"total": 0, "items": []}
    stmt = select(Club).where(
        Club.latitude.is_not(None), Club.longitude.is_not(None),
        or_(Club.address.ilike("%Санкт-Петербург%"), Club.address.ilike("%СПб%"), Club.address.ilike("%Петергоф%")),
    )
    if subject:
        stmt = stmt.where(Club.subject.ilike(subject))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(Club.name.ilike(pattern), Club.address.ilike(pattern), Club.note.ilike(pattern)))
    clubs = list((await db.execute(stmt.order_by(Club.name, Club.id))).scalars())
    items = []
    for club in clubs:
        distance = distance_km(lat, lon, float(club.latitude), float(club.longitude)) if lat is not None and lon is not None else None
        if radius_km is not None and distance is not None and distance > radius_km:
            continue
        items.append(club_item(club, distance))
    if lat is not None and lon is not None:
        items.sort(key=lambda item: (item["distance_km"], item["name"]))
    return {"total": len(items), "items": items}


@router.get("/clubs/{club_id}")
async def get_club(club_id: int, db: Db):
    club = await db.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Кружок не найден")
    return club_item(club)


@router.post("/clubs", status_code=201)
async def create_club(body: ClubWrite, db: Db):
    if body.subject not in SUBJECTS:
        raise HTTPException(400, "В тестовом режиме доступны математика и физика")
    club = Club(**body.model_dump())
    db.add(club)
    await db.commit()
    await db.refresh(club)
    return club_item(club)


@router.put("/clubs/{club_id}")
async def update_club(club_id: int, body: ClubWrite, db: Db):
    club = await db.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Кружок не найден")
    if body.subject not in SUBJECTS:
        raise HTTPException(400, "В тестовом режиме доступны математика и физика")
    for key, value in body.model_dump().items():
        setattr(club, key, value)
    await db.commit()
    await db.refresh(club)
    return club_item(club)


@router.delete("/clubs/{club_id}", status_code=204)
async def delete_club(club_id: int, db: Db):
    club = await db.get(Club, club_id)
    if club is None:
        raise HTTPException(404, "Кружок не найден")
    await db.delete(club)
    await db.commit()


@router.get("/sources")
async def list_sources(db: Db):
    sources = (await db.execute(select(CommunitySource).order_by(CommunitySource.id))).scalars()
    return {"items": [{"id": x.id, "source_url": x.source_url,
                        "example_places": x.example_places, "rows_count": x.rows_count} for x in sources]}


@router.get("/online")
async def list_online(db: Db, subject: str | None = None, q: str | None = None):
    stmt = select(OnlineCommunity).order_by(OnlineCommunity.sort_order, OnlineCommunity.name)
    if subject:
        stmt = stmt.where(OnlineCommunity.subject.ilike(subject))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(OnlineCommunity.name.ilike(pattern), OnlineCommunity.subject.ilike(pattern)))
    chats = (await db.execute(stmt)).scalars()
    return {"items": [online_item(chat) for chat in chats]}


@router.post("/online", status_code=201)
async def create_online(body: OnlineCommunityWrite, db: Db):
    chat = OnlineCommunity(**{**body.model_dump(), "url": str(body.url)})
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return online_item(chat)


@router.put("/online/{chat_id}")
async def update_online(chat_id: int, body: OnlineCommunityWrite, db: Db):
    chat = await db.get(OnlineCommunity, chat_id)
    if chat is None:
        raise HTTPException(404, "Чат не найден")
    for key, value in body.model_dump().items():
        setattr(chat, key, str(value) if key == "url" else value)
    await db.commit()
    await db.refresh(chat)
    return online_item(chat)


@router.delete("/online/{chat_id}", status_code=204)
async def delete_online(chat_id: int, db: Db):
    chat = await db.get(OnlineCommunity, chat_id)
    if chat is None:
        raise HTTPException(404, "Чат не найден")
    await db.delete(chat)
    await db.commit()
