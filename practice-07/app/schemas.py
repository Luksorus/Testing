from pydantic import BaseModel, ConfigDict, Field, model_validator


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Login(InputModel):
    username: str = Field(min_length=1, strict=True)
    password: str = Field(min_length=1, strict=True)


class CourseCreate(InputModel):
    name: str = Field(min_length=1, max_length=100, strict=True)
    price: float = Field(gt=0, strict=True)
    slots: int = Field(default=0, ge=0, le=30, strict=True)


class CourseReplace(CourseCreate):
    slots: int = Field(ge=0, le=30, strict=True)


class CoursePatch(InputModel):
    name: str | None = Field(default=None, min_length=1, max_length=100, strict=True)
    price: float | None = Field(default=None, gt=0, strict=True)
    slots: int | None = Field(default=None, ge=0, le=30, strict=True)

    @model_validator(mode="after")
    def require_nonempty_nonnull_fields(self):
        if not self.model_fields_set or any(
            getattr(self, name) is None for name in self.model_fields_set
        ):
            raise ValueError("Provide at least one non-null field")
        return self


class SlotChange(InputModel):
    delta: int = Field(strict=True)

    @model_validator(mode="after")
    def reject_zero(self):
        if self.delta == 0:
            raise ValueError("delta must not be zero")
        return self


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: float
    slots: int
