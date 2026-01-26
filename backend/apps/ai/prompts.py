"""
Prompt building for lesson plan generation.
"""

from typing import Any, Dict

from apps.lessons.models import Session


def build_lesson_plan_prompt(session: Session, context: Dict[str, Any]) -> tuple[str, str]:
    """
    Builds system and user prompts for lesson plan generation.

    Args:
        session: Session object
        context: Additional context (e.g., previous sessions, notes)

    Returns:
        Tuple (system_prompt, user_prompt)
    """
    student_ctx = context.get("student", {})
    lesson_ctx = context.get("lesson", {})
    previous_lessons = context.get("previous_lessons", [])

    student_name = student_ctx.get("full_name") or "[REDACTED]"
    student_grade = student_ctx.get("grade")
    subjects = student_ctx.get("subjects")
    lesson_notes = lesson_ctx.get("notes") or ""

    # System-Prompt: Rolle und Aufgabe
    system_prompt = """Du bist ein erfahrener Nachhilfelehrer, der strukturierte Unterrichtspläne erstellt.
Erstelle einen klaren, praxisorientierten Unterrichtsplan für eine Nachhilfestunde.
Der Plan soll:
- Eine klare Struktur haben (Einstieg, Hauptteil, Abschluss)
- Konkrete Übungen und Aufgaben enthalten
- Auf die Bedürfnisse des Schülers eingehen
- Realistisch für die verfügbare Zeit sein"""

    # User-Prompt: Kontext und Details
    user_prompt_parts = [
        "Erstelle einen Unterrichtsplan für eine Nachhilfestunde:",
        "",
        "**Schüler:**",
        f"- Name: {student_name}",
    ]

    if student_grade:
        user_prompt_parts.append(f"- Klasse: {student_grade}")

    if subjects:
        subject_list = subjects.split(",")
        subject = subject_list[0].strip() if subject_list else "Allgemein"
        user_prompt_parts.append(f"- Fach: {subject}")

    user_prompt_parts.extend(
        [
            "",
            "**Unterrichtsstunde:**",
            f"- Datum: {lesson_ctx.get('date', session.date)}",
            f"- Dauer: {lesson_ctx.get('duration_minutes', session.duration_minutes)} Minuten",
            f"- Status: {lesson_ctx.get('status', session.get_status_display())}",
        ]
    )

    if lesson_notes:
        user_prompt_parts.append(f"- Notizen: {lesson_notes}")

    # Kontext aus vorherigen Lessons
    if previous_lessons:
        user_prompt_parts.extend(
            [
                "",
                "**Vorherige Stunden:**",
            ]
        )
        for prev_lesson in previous_lessons[:3]:  # Max 3 vorherige
            user_prompt_parts.append(
                f"- {prev_lesson.get('date')}: {prev_lesson.get('notes') or 'Keine Notizen'}"
            )

    student_notes = student_ctx.get("notes")
    if student_notes:
        user_prompt_parts.extend(
            [
                "",
                f"**Schüler-Notizen:** {student_notes}",
            ]
        )

    user_prompt_parts.extend(
        [
            "",
            "Erstelle einen strukturierten Unterrichtsplan für diese Stunde.",
        ]
    )

    user_prompt = "\n".join(user_prompt_parts)

    return system_prompt, user_prompt


def extract_subject_from_student(student) -> str:
    """
    Extrahiert das Hauptfach aus den Student-Subjects.

    Args:
        student: Student-Objekt

    Returns:
        Fach-String (z. B. "Mathe", "Deutsch")
    """
    if not student.subjects:
        return "Allgemein"

    subjects = student.subjects.split(",")
    return subjects[0].strip() if subjects else "Allgemein"
