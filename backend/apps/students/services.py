"""
Services for student-related operations.
"""

from difflib import SequenceMatcher
from typing import List, Tuple

from apps.students.models import Student


class StudentSearchService:
    """Service for searching students by name with fuzzy matching."""

    @staticmethod
    def similarity_ratio(a: str, b: str) -> float:
        """
        Calculate similarity ratio between two strings.

        Args:
            a: First string
            b: Second string

        Returns:
            Similarity ratio between 0.0 and 1.0
        """
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def search_by_name(name: str, threshold: float = 0.7, user=None) -> List[Tuple[Student, float]]:
        """
        Search for students by name using fuzzy matching.

        Args:
            name: Name to search for (can be full name, first name, or last name)
            threshold: Minimum similarity ratio (default: 0.7 = 70%)
            user: Optional - filter to this user's students (for multi-tenancy)

        Returns:
            List of tuples (Student, similarity_ratio) sorted by similarity (highest first)
        """
        if not name or not name.strip():
            return []

        name_lower = name.strip().lower()
        results = []

        # Get students (optionally filtered by user)
        all_students = Student.objects.all()
        if user:
            all_students = all_students.filter(user=user)

        for student in all_students:
            # Calculate similarity for full name
            full_name = student.full_name.lower()
            full_name_ratio = StudentSearchService.similarity_ratio(name_lower, full_name)

            # Calculate similarity for first name
            first_name_ratio = StudentSearchService.similarity_ratio(
                name_lower, student.first_name.lower()
            )

            # Calculate similarity for last name
            last_name_ratio = StudentSearchService.similarity_ratio(
                name_lower, student.last_name.lower()
            )

            # Use the highest similarity ratio
            max_ratio = max(full_name_ratio, first_name_ratio, last_name_ratio)

            # Also check if name is contained in full name (for partial matches)
            if (
                name_lower in full_name
                or name_lower in student.first_name.lower()
                or name_lower in student.last_name.lower()
            ):
                # Boost similarity for substring matches
                max_ratio = max(max_ratio, 0.8)

            # Add to results if above threshold
            if max_ratio >= threshold:
                results.append((student, max_ratio))

        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    @staticmethod
    def find_exact_match(name: str, user=None) -> Student | None:
        """
        Find exact match for a student name.

        Args:
            name: Name to search for
            user: Optional - filter to this user's students (for multi-tenancy)

        Returns:
            Student if exact match found, None otherwise
        """
        if not name or not name.strip():
            return None

        name_lower = name.strip().lower()

        # Try exact match on full name
        students_qs = Student.objects.all()
        if user:
            students_qs = students_qs.filter(user=user)
        for student in students_qs:
            if student.full_name.lower() == name_lower:
                return student

        return None
