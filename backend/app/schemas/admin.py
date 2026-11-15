from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    slug: str = Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    published: bool = False


class CoursePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    published: bool | None = None


class ModuleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0, le=10000)


class ModulePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    position: int | None = Field(default=None, ge=0, le=10000)


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=20000)
    duration_seconds: int = Field(default=0, ge=0, le=86400)
    position: int = Field(ge=0, le=10000)


class LessonPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, max_length=20000)
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    position: int | None = Field(default=None, ge=0, le=10000)
