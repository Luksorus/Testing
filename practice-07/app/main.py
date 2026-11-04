import hmac
import secrets
import time
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import Course, build_session_factory
from .rates import RateServiceError, RatesClient, get_rates_client
from .schemas import CourseCreate, CourseOut, CoursePatch, CourseReplace, Login, SlotChange

# Deliberately public demo credentials; never use these accounts in production.
DEMO_USERS = {"admin": ("admin-pass", "admin"), "viewer": ("viewer-pass", "viewer")}
bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def get_role(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    token = request.app.state.tokens.get(credentials.credentials) if credentials else None
    if token is None or token[1] <= time.monotonic():
        raise HTTPException(401, "Invalid or missing token", headers={"WWW-Authenticate": "Bearer"})
    return token[0]


def require_admin(role: Annotated[str, Depends(get_role)]):
    if role != "admin":
        raise HTTPException(403, "Admin role required")


DB = Annotated[Session, Depends(get_db)]
Reader = Annotated[str, Depends(get_role)]


def find_course(db: Session, course_id: int):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "Course not found")
    return course


def save_course(db: Session, course: Course):
    db.add(course)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Course name already exists") from exc
    db.refresh(course)
    return course


def create_app(session_factory=None):
    app = FastAPI(title="Course inventory API", version="1.0")
    app.state.session_factory = session_factory or build_session_factory()
    app.state.tokens = {}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/login")
    def login(body: Login):
        user = DEMO_USERS.get(body.username)
        if user is None or not hmac.compare_digest(body.password, user[0]):
            raise HTTPException(401, "Invalid credentials")
        token = secrets.token_urlsafe(32)
        app.state.tokens[token] = (user[1], time.monotonic() + 3600)
        return {"access_token": token, "token_type": "bearer"}

    @app.post("/courses", status_code=201, response_model=CourseOut,
              dependencies=[Depends(require_admin)])
    def create_course(body: CourseCreate, db: DB):
        return save_course(db, Course(**body.model_dump()))

    @app.get("/courses", response_model=list[CourseOut])
    def list_courses(
        db: DB, role: Reader, q: str | None = None,
        min_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        max_price: Annotated[float | None, Query(ge=0, allow_inf_nan=False)] = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        if min_price is not None and max_price is not None and min_price > max_price:
            raise HTTPException(422, "min_price exceeds max_price")
        query = select(Course)
        if min_price is not None:
            query = query.where(Course.price >= min_price)
        if max_price is not None:
            query = query.where(Course.price <= max_price)
        courses = db.scalars(query.order_by(Course.id)).all()
        if q is not None:
            courses = [course for course in courses if q.casefold() in course.name.casefold()]
        return courses[offset:offset + limit]

    @app.get("/courses/{course_id}", response_model=CourseOut)
    def get_course(course_id: int, db: DB, role: Reader):
        return find_course(db, course_id)

    @app.put("/courses/{course_id}", response_model=CourseOut,
             dependencies=[Depends(require_admin)])
    def replace_course(course_id: int, body: CourseReplace, db: DB):
        course = find_course(db, course_id)
        for name, value in body.model_dump().items():
            setattr(course, name, value)
        return save_course(db, course)

    @app.patch("/courses/{course_id}", response_model=CourseOut,
               dependencies=[Depends(require_admin)])
    def patch_course(course_id: int, body: CoursePatch, db: DB):
        course = find_course(db, course_id)
        for name, value in body.model_dump(exclude_unset=True).items():
            setattr(course, name, value)
        return save_course(db, course)

    @app.delete("/courses/{course_id}", status_code=204,
                dependencies=[Depends(require_admin)])
    def delete_course(course_id: int, db: DB):
        course = find_course(db, course_id)
        db.delete(course)
        db.commit()
        return Response(status_code=204)

    @app.post("/courses/{course_id}/slots", response_model=CourseOut,
              dependencies=[Depends(require_admin)])
    def change_slots(course_id: int, body: SlotChange, db: DB):
        find_course(db, course_id)
        # Bound checking and update are one SQL statement to avoid lost updates.
        statement = update(Course).where(
            Course.id == course_id,
            Course.slots + body.delta >= 0,
            Course.slots + body.delta <= 30,
        ).values(slots=Course.slots + body.delta).returning(Course)
        course = db.execute(statement).scalar_one_or_none()
        if course is None:
            db.rollback()
            raise HTTPException(409, "Slots must remain between 0 and 30")
        db.commit()
        db.refresh(course)
        return course

    @app.get("/courses/{course_id}/price")
    def currency_price(
        course_id: int, db: DB, role: Reader,
        currency: Literal["USD", "EUR"],
        rates: Annotated[RatesClient, Depends(get_rates_client)],
    ):
        course = find_course(db, course_id)
        try:
            rate = rates.get_rate(currency)
        except RateServiceError as exc:
            raise HTTPException(502, "Rates unavailable") from exc
        return {"currency": currency, "price": course.price * rate}

    return app
