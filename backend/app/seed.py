from sqlmodel import Session, select

from app.db.models import Course, Lesson, Module
from app.db.session import engine


def seed() -> None:
    with Session(engine) as session:
        if session.exec(select(Course).where(Course.slug == "python-foundations")).first():
            print("Seed data already present")
            return
        course = Course(
            slug="python-foundations",
            title="Python Foundations",
            description="A local demonstration course covering core Python concepts.",
        )
        module = Module(title="Getting Started", position=0, course=course)
        module.lessons = [
            Lesson(
                title="Values and variables",
                content="Learn how Python stores values in named variables.",
                duration_seconds=300,
                position=0,
            ),
            Lesson(
                title="Functions",
                content="Group reusable instructions into functions.",
                duration_seconds=420,
                position=1,
            ),
        ]
        course.modules = [module]
        session.add(course)
        session.commit()
        print("Seeded Python Foundations course; create a user via /api/v1/auth/register to enroll")


if __name__ == "__main__":
    seed()
