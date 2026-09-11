from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table
from sqlalchemy.orm import relationship
from database import Base

teacher_class_association = Table(
    "teacher_class_association",
    Base.metadata,
    Column("teacher_id", Integer, ForeignKey("teachers.id")),
    Column("class_id", Integer, ForeignKey("classes.id")),
)


class AdminSettings(Base):
    """Single-row table holding the administrator's password hash."""
    __tablename__ = "admin_settings"
    id = Column(Integer, primary_key=True)
    password_hash = Column(String, nullable=False)


class SchoolClass(Base):
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)

    students = relationship("Student", back_populates="school_class")
    teachers = relationship(
        "Teacher", secondary=teacher_class_association, back_populates="classes"
    )


class Teacher(Base):
    __tablename__ = "teachers"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)

    classes = relationship(
        "SchoolClass", secondary=teacher_class_association, back_populates="teachers"
    )


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    reg_no = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)

    school_class = relationship("SchoolClass", back_populates="students")
    results = relationship(
        "Result", back_populates="student", cascade="all, delete-orphan"
    )


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    term = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    score = Column(Float, nullable=False)

    student = relationship("Student", back_populates="results")
