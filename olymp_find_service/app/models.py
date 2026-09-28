from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class University(Base):
    __tablename__ = "university"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    cities: Mapped[list["UniversityCity"]] = relationship("UniversityCity", back_populates="university")
    programs: Mapped[list["ProgramUniversity"]] = relationship("ProgramUniversity", back_populates="university")
    hosted_olympiads: Mapped[list["Olympiad"]] = relationship("Olympiad", back_populates="host_university")


class City(Base):
    __tablename__ = "city"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class UniversityCity(Base):
    __tablename__ = "universities_cities"

    university_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("university.id", ondelete="CASCADE"), primary_key=True
    )
    city_id: Mapped[int] = mapped_column(Integer, ForeignKey("city.id", ondelete="CASCADE"), primary_key=True)

    university: Mapped[University] = relationship("University", back_populates="cities")
    city: Mapped[City] = relationship("City")


class Program(Base):
    __tablename__ = "program"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text, unique=True)

    universities: Mapped[list["ProgramUniversity"]] = relationship("ProgramUniversity", back_populates="program")


class ProgramUniversity(Base):
    __tablename__ = "programs_universities"

    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.id", ondelete="CASCADE"), primary_key=True)
    university_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("university.id", ondelete="CASCADE"), primary_key=True
    )

    program: Mapped[Program] = relationship("Program", back_populates="universities")
    university: Mapped[University] = relationship("University", back_populates="programs")


class Subject(Base):
    __tablename__ = "subject"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)

    olympiad_links: Mapped[list["SubjectOlympiad"]] = relationship("SubjectOlympiad", back_populates="subject")


class Olympiad(Base):
    __tablename__ = "olympiad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_university_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("university.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    complexity: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    host_university: Mapped[University] = relationship("University", back_populates="hosted_olympiads")
    subjects: Mapped[list["SubjectOlympiad"]] = relationship("SubjectOlympiad", back_populates="olympiad")
    stages: Mapped[list["Stage"]] = relationship("Stage", back_populates="olympiad")
    benefits: Mapped[list["Benefit"]] = relationship("Benefit", back_populates="olympiad")


class SubjectOlympiad(Base):
    __tablename__ = "subject_olympiad"
    __table_args__ = (UniqueConstraint("subject_id", "olympiad_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    olympiad_id: Mapped[int] = mapped_column(Integer, ForeignKey("olympiad.id", ondelete="CASCADE"), nullable=False)

    subject: Mapped[Subject] = relationship("Subject", back_populates="olympiad_links")
    olympiad: Mapped[Olympiad] = relationship("Olympiad", back_populates="subjects")


class Stage(Base):
    __tablename__ = "stage"

    stage_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    olymp_id: Mapped[int] = mapped_column(Integer, ForeignKey("olympiad.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    olympiad: Mapped[Olympiad] = relationship("Olympiad", back_populates="stages")


class Benefit(Base):
    __tablename__ = "benefit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    olympiad_id: Mapped[int] = mapped_column(Integer, ForeignKey("olympiad.id", ondelete="CASCADE"), nullable=False)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("program.id", ondelete="CASCADE"), nullable=False)
    university_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("university.id", ondelete="CASCADE"), nullable=False
    )
    benefit_type: Mapped[str] = mapped_column(Text, nullable=False)

    olympiad: Mapped[Olympiad] = relationship("Olympiad", back_populates="benefits")
    program: Mapped[Program] = relationship("Program")
    university: Mapped[University] = relationship("University")


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (UniqueConstraint("user_id", "olympiad_id", name="favorite_user_olympiad_pk"),)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    olympiad_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subject_olympiad.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    olympiad: Mapped[SubjectOlympiad] = relationship("SubjectOlympiad")


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    subject: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)


class CommunitySource(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_url: Mapped[str | None] = mapped_column(Text)
    example_places: Mapped[str | None] = mapped_column(Text)
    rows_count: Mapped[int | None] = mapped_column(Integer)


class OnlineCommunity(Base):
    __tablename__ = "online_communities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
