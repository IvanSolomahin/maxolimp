from datetime import datetime

from pydantic import BaseModel, Field


class SubjectRef(BaseModel):
    id: int
    name: str


class HostUniversityRef(BaseModel):
    id: int
    name: str


class UniversityListItem(BaseModel):
    id: int
    name: str
    cities: list[str]


class PaginatedUniversities(BaseModel):
    total: int
    page: int
    size: int
    items: list[UniversityListItem]


class ProgramItem(BaseModel):
    id: int
    name: str
    code: str


class PaginatedPrograms(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProgramItem]


class ProgramWithUniversityItem(BaseModel):
    id: int
    name: str
    code: str
    university_id: int


class PaginatedProgramsWithUniversity(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProgramWithUniversityItem]


class PaginatedSubjects(BaseModel):
    total: int
    page: int
    size: int
    items: list[SubjectRef]


class BenefitTypeRef(BaseModel):
    type: str


class RecommendationItem(BaseModel):
    id: int
    name: str
    complexity: int
    benefit: BenefitTypeRef


class PaginatedRecommendations(BaseModel):
    total: int
    page: int
    size: int
    items: list[RecommendationItem]


class OlympiadDetail(BaseModel):
    id: int
    name: str
    complexity: int
    description: str
    host_university: HostUniversityRef


class StageItem(BaseModel):
    id: int
    name: str
    is_online: bool
    location: str | None
    start_date: datetime
    end_date: datetime


class StagesResponse(BaseModel):
    items: list[StageItem]


class BenefitItem(BaseModel):
    id: int
    university_id: int
    program_id: int
    benefit_type: str


class BenefitsResponse(BaseModel):
    items: list[BenefitItem]


class FavoriteItem(BaseModel):
    olympiad_id: int
    name: str
    complexity: int
    benefit_type: str | None


class PaginatedFavorites(BaseModel):
    total: int
    page: int
    size: int
    items: list[FavoriteItem]


class AddFavoriteRequest(BaseModel):
    olympiad_id: int = Field(ge=1)


class FavoriteMutationResponse(BaseModel):
    success: bool = True
    olympiad_id: int
