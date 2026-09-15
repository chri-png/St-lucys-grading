import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import Base, engine, get_db
from report_card import build_report_card_pdf

Base.metadata.create_all(bind=engine)

# Lightweight migration: add the "comment" column to results if it doesn't
# already exist (create_all only creates missing tables, not new columns
# on tables that already exist in a live database).
try:
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE results ADD COLUMN comment VARCHAR"))
except Exception:
    pass  # column already exists — nothing to do

app = FastAPI(title="St. Lucy's School for the Blind — Grading System API")

# Allow the frontend to call this API from any origin. If you host the
# frontend on a different domain than the backend, this keeps it working;
# you can restrict this list once you know your frontend's final URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_admin_row(db: Session) -> models.AdminSettings:
    admin = db.query(models.AdminSettings).first()
    if not admin:
        default_password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin123")
        admin = models.AdminSettings(password_hash=auth.hash_password(default_password))
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin


def result_to_item(r: models.Result) -> schemas.ResultItem:
    return schemas.ResultItem(id=r.id, term=r.term, subject=r.subject, score=r.score, comment=r.comment)


def student_to_results_response(student: models.Student) -> schemas.StudentResultsResponse:
    return schemas.StudentResultsResponse(
        reg_no=student.reg_no,
        name=student.name,
        class_name=student.school_class.name if student.school_class else None,
        results=[result_to_item(r) for r in student.results],
    )


def report_card_response(student: models.Student) -> Response:
    pdf_bytes = build_report_card_pdf(student)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{student.reg_no}_report_card.pdf"'},
    )


# ---------------------------------------------------------------------
# Public endpoints (no login required)
# ---------------------------------------------------------------------

@app.get("/api/public/classes", response_model=list[schemas.ClassResponse])
def list_classes_public(db: Session = Depends(get_db)):
    classes = db.query(models.SchoolClass).order_by(models.SchoolClass.name).all()
    return [schemas.ClassResponse(name=c.name) for c in classes]


# ---------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------

@app.post("/api/auth/admin/login", response_model=schemas.TokenResponse)
def admin_login(payload: schemas.AdminLoginRequest, db: Session = Depends(get_db)):
    admin = ensure_admin_row(db)
    if not auth.verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect administrator password.")
    token = auth.create_token("admin", "admin")
    return schemas.TokenResponse(token=token, role="admin", display_name="Administrator")


@app.post("/api/auth/teacher/login", response_model=schemas.TokenResponse)
def teacher_login(payload: schemas.TeacherLoginRequest, db: Session = Depends(get_db)):
    teacher = db.query(models.Teacher).filter_by(username=payload.username).first()
    if not teacher or not auth.verify_password(payload.password, teacher.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = auth.create_token("teacher", teacher.username)
    return schemas.TokenResponse(token=token, role="teacher", display_name=teacher.name)


@app.post("/api/auth/student/login", response_model=schemas.TokenResponse)
def student_login(payload: schemas.StudentLoginRequest, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter_by(reg_no=payload.reg_no).first()
    class_name = student.school_class.name if student and student.school_class else None
    if (
        not student
        or student.name.strip().lower() != payload.name.strip().lower()
        or class_name != payload.class_name
    ):
        raise HTTPException(
            status_code=401,
            detail="We could not find a matching student record. Check your registration number, name, and class.",
        )
    token = auth.create_token("student", student.reg_no)
    return schemas.TokenResponse(token=token, role="student", display_name=student.name)


# ---------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------

@app.get("/api/admin/classes", response_model=list[schemas.ClassResponse])
def admin_list_classes(
    db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    classes = db.query(models.SchoolClass).order_by(models.SchoolClass.name).all()
    return [schemas.ClassResponse(name=c.name) for c in classes]


@app.post("/api/admin/classes", response_model=schemas.ClassResponse)
def admin_add_class(
    payload: schemas.ClassCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    existing = db.query(models.SchoolClass).filter_by(name=payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="That class already exists.")
    school_class = models.SchoolClass(name=payload.name)
    db.add(school_class)
    db.commit()
    return schemas.ClassResponse(name=school_class.name)


@app.delete("/api/admin/classes/{class_name}")
def admin_delete_class(
    class_name: str,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    school_class = db.query(models.SchoolClass).filter_by(name=class_name).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found.")
    db.delete(school_class)
    db.commit()
    return {"detail": "Class removed."}


@app.get("/api/admin/teachers", response_model=list[schemas.TeacherResponse])
def admin_list_teachers(
    db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    teachers = db.query(models.Teacher).order_by(models.Teacher.name).all()
    return [
        schemas.TeacherResponse(
            name=t.name, username=t.username, classes=[c.name for c in t.classes]
        )
        for t in teachers
    ]


@app.post("/api/admin/teachers", response_model=schemas.TeacherResponse)
def admin_add_teacher(
    payload: schemas.TeacherCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    if db.query(models.Teacher).filter_by(username=payload.username).first():
        raise HTTPException(status_code=400, detail="That username is already taken.")
    classes = (
        db.query(models.SchoolClass)
        .filter(models.SchoolClass.name.in_(payload.classes))
        .all()
    )
    teacher = models.Teacher(
        username=payload.username,
        password_hash=auth.hash_password(payload.password),
        name=payload.name,
        classes=classes,
    )
    db.add(teacher)
    db.commit()
    return schemas.TeacherResponse(
        name=teacher.name, username=teacher.username, classes=[c.name for c in classes]
    )


@app.put("/api/admin/teachers/{username}/classes", response_model=schemas.TeacherResponse)
def admin_update_teacher_classes(
    username: str,
    payload: schemas.TeacherUpdateClassesRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    teacher = db.query(models.Teacher).filter_by(username=username).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    classes = (
        db.query(models.SchoolClass)
        .filter(models.SchoolClass.name.in_(payload.classes))
        .all()
    )
    teacher.classes = classes
    db.commit()
    return schemas.TeacherResponse(
        name=teacher.name, username=teacher.username, classes=[c.name for c in classes]
    )


@app.put("/api/admin/teachers/{username}/password")
def admin_reset_teacher_password(
    username: str,
    payload: schemas.TeacherPasswordResetRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    teacher = db.query(models.Teacher).filter_by(username=username).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    teacher.password_hash = auth.hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password reset for " + teacher.name + "."}


@app.get("/api/admin/students", response_model=list[schemas.StudentSummaryResponse])
def admin_list_students(
    db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    students = db.query(models.Student).order_by(models.Student.name).all()
    return [
        schemas.StudentSummaryResponse(
            reg_no=s.reg_no,
            name=s.name,
            class_name=s.school_class.name if s.school_class else None,
            result_count=len(s.results),
        )
        for s in students
    ]


@app.post("/api/admin/students", response_model=schemas.StudentSummaryResponse)
def admin_add_student(
    payload: schemas.StudentCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    if db.query(models.Student).filter_by(reg_no=payload.reg_no).first():
        raise HTTPException(
            status_code=400, detail="A student with that registration number already exists."
        )
    school_class = db.query(models.SchoolClass).filter_by(name=payload.class_name).first()
    if not school_class:
        raise HTTPException(status_code=400, detail="That class does not exist.")
    student = models.Student(reg_no=payload.reg_no, name=payload.name, school_class=school_class)
    db.add(student)
    db.commit()
    return schemas.StudentSummaryResponse(
        reg_no=student.reg_no, name=student.name, class_name=school_class.name, result_count=0
    )


@app.get("/api/admin/students/{reg_no}/results", response_model=schemas.StudentResultsResponse)
def admin_view_student_results(
    reg_no: str, db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    student = db.query(models.Student).filter_by(reg_no=reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="No student found with that registration number.")
    return student_to_results_response(student)


@app.get("/api/admin/students/{reg_no}/report-card")
def admin_report_card(
    reg_no: str, db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    student = db.query(models.Student).filter_by(reg_no=reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="No student found with that registration number.")
    return report_card_response(student)


@app.get("/api/admin/dashboard-stats")
def admin_dashboard_stats(
    db: Session = Depends(get_db), _=Depends(auth.require_role("admin"))
):
    total_classes = db.query(models.SchoolClass).count()
    total_teachers = db.query(models.Teacher).count()
    total_students = db.query(models.Student).count()

    all_results = db.query(models.Result).all()
    subject_totals = {}
    for r in all_results:
        key = (r.student_id, r.term, r.subject)
        subject_totals[key] = subject_totals.get(key, 0.0) + r.score

    average_performance = (
        sum(subject_totals.values()) / len(subject_totals) if subject_totals else None
    )

    return {
        "total_classes": total_classes,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "average_performance": average_performance,
        "recorded_subject_entries": len(subject_totals),
    }


@app.put("/api/admin/password")
def admin_change_password(
    payload: schemas.AdminPasswordChangeRequest,
    db: Session = Depends(get_db),
    _=Depends(auth.require_role("admin")),
):
    admin = ensure_admin_row(db)
    admin.password_hash = auth.hash_password(payload.new_password)
    db.commit()
    return {"detail": "Administrator password updated."}


# ---------------------------------------------------------------------
# Teacher endpoints
# ---------------------------------------------------------------------

def get_teacher_or_403(db: Session, username: str) -> models.Teacher:
    teacher = db.query(models.Teacher).filter_by(username=username).first()
    if not teacher:
        raise HTTPException(status_code=403, detail="Teacher account not found.")
    return teacher


@app.get("/api/teacher/me", response_model=schemas.TeacherResponse)
def teacher_me(
    db: Session = Depends(get_db), token=Depends(auth.require_role("teacher"))
):
    teacher = get_teacher_or_403(db, token["sub"])
    return schemas.TeacherResponse(
        name=teacher.name, username=teacher.username, classes=[c.name for c in teacher.classes]
    )


@app.get("/api/teacher/dashboard-stats")
def teacher_dashboard_stats(
    db: Session = Depends(get_db), token=Depends(auth.require_role("teacher"))
):
    teacher = get_teacher_or_403(db, token["sub"])
    class_ids = [c.id for c in teacher.classes]
    students = (
        db.query(models.Student).filter(models.Student.class_id.in_(class_ids)).all()
        if class_ids else []
    )
    subject_totals = {}
    for s in students:
        for r in s.results:
            key = (s.id, r.term, r.subject)
            subject_totals[key] = subject_totals.get(key, 0.0) + r.score

    average_performance = (
        sum(subject_totals.values()) / len(subject_totals) if subject_totals else None
    )

    return {
        "total_classes": len(class_ids),
        "total_students": len(students),
        "average_performance": average_performance,
    }


@app.post("/api/teacher/students", response_model=schemas.StudentSummaryResponse)
def teacher_set_student_class(
    payload: schemas.TeacherSetStudentClassRequest,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    allowed_class_names = {c.name for c in teacher.classes}
    if payload.class_name not in allowed_class_names:
        raise HTTPException(status_code=403, detail="You do not have access to that class.")

    school_class = db.query(models.SchoolClass).filter_by(name=payload.class_name).first()
    student = db.query(models.Student).filter_by(reg_no=payload.reg_no).first()

    if student:
        student.school_class = school_class
        if payload.name:
            student.name = payload.name
    else:
        if not payload.name:
            raise HTTPException(
                status_code=400, detail="Please provide the student's full name to create a new record."
            )
        student = models.Student(reg_no=payload.reg_no, name=payload.name, school_class=school_class)
        db.add(student)

    db.commit()
    db.refresh(student)
    return schemas.StudentSummaryResponse(
        reg_no=student.reg_no,
        name=student.name,
        class_name=school_class.name,
        result_count=len(student.results),
    )


@app.get(
    "/api/teacher/classes/{class_name}/students",
    response_model=list[schemas.StudentSummaryResponse],
)
def teacher_class_roster(
    class_name: str,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    if class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(status_code=403, detail="You do not have access to that class.")
    school_class = db.query(models.SchoolClass).filter_by(name=class_name).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found.")
    return [
        schemas.StudentSummaryResponse(
            reg_no=s.reg_no, name=s.name, class_name=class_name, result_count=len(s.results)
        )
        for s in sorted(school_class.students, key=lambda s: s.name)
    ]


@app.post("/api/teacher/results")
def teacher_add_result(
    payload: schemas.ResultCreateRequest,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    student = db.query(models.Student).filter_by(reg_no=payload.reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    student_class_name = student.school_class.name if student.school_class else None
    if student_class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(
            status_code=403, detail="You do not have access to this student's class."
        )
    result = models.Result(
        student_id=student.id,
        term=payload.term,
        subject=payload.subject,
        score=payload.score,
        comment=payload.comment,
    )
    db.add(result)
    db.commit()
    return {"detail": "Result recorded."}


@app.get(
    "/api/teacher/students/{reg_no}/results", response_model=schemas.StudentResultsResponse
)
def teacher_view_student_results(
    reg_no: str,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    student = db.query(models.Student).filter_by(reg_no=reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    student_class_name = student.school_class.name if student.school_class else None
    if student_class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(
            status_code=403, detail="You do not have access to this student's class."
        )
    return student_to_results_response(student)


@app.get("/api/teacher/students/{reg_no}/report-card")
def teacher_report_card(
    reg_no: str,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    student = db.query(models.Student).filter_by(reg_no=reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    student_class_name = student.school_class.name if student.school_class else None
    if student_class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(
            status_code=403, detail="You do not have access to this student's class."
        )
    return report_card_response(student)


# ---------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------

@app.delete("/api/teacher/students/{reg_no}/class")
def teacher_remove_student_from_class(
    reg_no: str,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    student = db.query(models.Student).filter_by(reg_no=reg_no).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")
    student_class_name = student.school_class.name if student.school_class else None
    if student_class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(status_code=403, detail="You do not have access to this student's class.")
    student.school_class = None
    db.commit()
    return {"detail": "Removed " + student.name + " from the class."}


def get_teacher_result_or_403(db: Session, teacher: models.Teacher, result_id: int) -> models.Result:
    result = db.query(models.Result).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found.")
    student_class_name = result.student.school_class.name if result.student.school_class else None
    if student_class_name not in {c.name for c in teacher.classes}:
        raise HTTPException(status_code=403, detail="You do not have access to this result.")
    return result


@app.put("/api/teacher/results/{result_id}")
def teacher_edit_result(
    result_id: int,
    payload: schemas.ResultUpdateRequest,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    result = get_teacher_result_or_403(db, teacher, result_id)
    result.term = payload.term
    result.subject = payload.subject
    result.score = payload.score
    result.comment = payload.comment
    db.commit()
    return {"detail": "Result updated."}


@app.delete("/api/teacher/results/{result_id}")
def teacher_delete_result(
    result_id: int,
    db: Session = Depends(get_db),
    token=Depends(auth.require_role("teacher")),
):
    teacher = get_teacher_or_403(db, token["sub"])
    result = get_teacher_result_or_403(db, teacher, result_id)
    db.delete(result)
    db.commit()
    return {"detail": "Result deleted."}


@app.get("/api/student/me", response_model=schemas.StudentResultsResponse)
def student_me(
    db: Session = Depends(get_db), token=Depends(auth.require_role("student"))
):
    student = db.query(models.Student).filter_by(reg_no=token["sub"]).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return student_to_results_response(student)


@app.get("/api/student/me/report-card")
def student_report_card(
    db: Session = Depends(get_db), token=Depends(auth.require_role("student"))
):
    student = db.query(models.Student).filter_by(reg_no=token["sub"]).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return report_card_response(student)


# ---------------------------------------------------------------------
# Serve the frontend (static/index.html) at the site root.
# Keep this mount LAST so it doesn't shadow the /api routes above.
# ---------------------------------------------------------------------
app.mount("/", StaticFiles(directory="static", html=True), name="static")
