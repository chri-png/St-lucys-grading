from typing import List, Optional
from pydantic import BaseModel, Field


# ---- Auth ----
class AdminLoginRequest(BaseModel):
    password: str


class TeacherLoginRequest(BaseModel):
    username: str
    password: str


class StudentLoginRequest(BaseModel):
    reg_no: str
    name: str
    class_name: str


class TokenResponse(BaseModel):
    token: str
    role: str
    display_name: str


# ---- Classes ----
class ClassCreateRequest(BaseModel):
    name: str = Field(min_length=1)


class ClassResponse(BaseModel):
    name: str


# ---- Subjects ----
class SubjectCreateRequest(BaseModel):
    name: str = Field(min_length=1)


class SubjectResponse(BaseModel):
    name: str


# ---- Teachers ----
class TeacherCreateRequest(BaseModel):
    name: str
    username: str
    password: str
    classes: List[str] = []


class TeacherUpdateClassesRequest(BaseModel):
    classes: List[str] = []


class TeacherPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=4)


class TeacherResponse(BaseModel):
    name: str
    username: str
    classes: List[str]


# ---- Students ----
class StudentCreateRequest(BaseModel):
    reg_no: str
    name: str
    class_name: str


class TeacherSetStudentClassRequest(BaseModel):
    reg_no: str
    name: Optional[str] = None
    class_name: str


class StudentSummaryResponse(BaseModel):
    reg_no: str
    name: str
    class_name: Optional[str]
    result_count: int


# ---- Results ----
class ResultCreateRequest(BaseModel):
    reg_no: str
    term: str
    subject: str
    score: float = Field(ge=0, le=100)
    comment: Optional[str] = None


class ResultUpdateRequest(BaseModel):
    term: str
    subject: str
    score: float = Field(ge=0, le=100)
    comment: Optional[str] = None


class ResultItem(BaseModel):
    id: int
    term: str
    subject: str
    score: float
    comment: Optional[str] = None


class StudentResultsResponse(BaseModel):
    reg_no: str
    name: str
    class_name: Optional[str]
    results: List[ResultItem]


# ---- Admin settings ----
class AdminPasswordChangeRequest(BaseModel):
    new_password: str = Field(min_length=4)
