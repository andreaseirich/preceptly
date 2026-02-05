"""
Tests for seed_demo_data management command.
"""

from apps.blocked_times.models import BlockedTime
from apps.contracts.models import Contract, ContractMonthlyPlan
from apps.core.models import UserProfile
from apps.lesson_plans.models import LessonPlan
from apps.lessons.models import Lesson
from apps.lessons.recurring_models import RecurringLesson
from apps.students.models import Student
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase


class SeedDemoDataTest(TestCase):
    """Tests for seed_demo_data command."""

    def test_seed_demo_data_creates_premium_user_with_lesson_plan(self):
        """Test: seed_demo_data creates premium user with lesson plan."""
        call_command("seed_demo_data", "--clear")

        # Check premium user exists
        premium_user = User.objects.filter(username="demo_premium").first()
        self.assertIsNotNone(premium_user)

        # Check premium profile
        profile = UserProfile.objects.filter(user=premium_user).first()
        self.assertIsNotNone(profile)
        self.assertTrue(profile.is_premium)

        # Check lesson plan exists
        lesson_plans = LessonPlan.objects.all()
        self.assertGreater(lesson_plans.count(), 0)

        # Check at least one lesson plan is linked to a lesson
        lesson_plans_with_lessons = LessonPlan.objects.exclude(lesson__isnull=True)
        self.assertGreater(lesson_plans_with_lessons.count(), 0)

    def test_seed_demo_data_creates_recurring_lessons(self):
        """Test: seed_demo_data creates recurring lessons."""
        call_command("seed_demo_data", "--clear")

        # Check recurring lessons exist
        recurring_lessons = RecurringLesson.objects.all()
        self.assertGreater(recurring_lessons.count(), 0)

        # Check that lessons were generated from recurring lessons
        lessons = Lesson.objects.all()
        self.assertGreater(lessons.count(), 0)

        # Check at least one recurring lesson has weekdays set
        recurring_with_weekdays = (
            RecurringLesson.objects.filter(monday=True)
            | RecurringLesson.objects.filter(tuesday=True)
            | RecurringLesson.objects.filter(wednesday=True)
        )
        self.assertGreater(recurring_with_weekdays.count(), 0)

    def test_seed_demo_data_creates_contract_monthly_plans(self):
        """Test: seed_demo_data creates contract monthly plans."""
        call_command("seed_demo_data", "--clear")

        # Check monthly plans exist
        monthly_plans = ContractMonthlyPlan.objects.all()
        self.assertGreater(monthly_plans.count(), 0)

    def test_seed_demo_data_creates_blocked_times(self):
        """Test: seed_demo_data creates blocked times."""
        call_command("seed_demo_data", "--clear")

        # Check blocked times exist
        blocked_times = BlockedTime.objects.all()
        self.assertGreater(blocked_times.count(), 0)

    def test_seed_demo_data_creates_multiple_students_and_contracts(self):
        """Test: seed_demo_data creates multiple students and contracts."""
        call_command("seed_demo_data", "--clear")

        # Check students exist
        students = Student.objects.all()
        self.assertGreaterEqual(students.count(), 3)

        # Check contracts exist
        contracts = Contract.objects.all()
        self.assertGreaterEqual(contracts.count(), 3)

    def test_seed_demo_data_creates_non_premium_user(self):
        """Test: seed_demo_data creates non-premium user."""
        call_command("seed_demo_data", "--clear")

        # Check non-premium user exists
        non_premium_user = User.objects.filter(username="demo_user").first()
        self.assertIsNotNone(non_premium_user)

        # Check non-premium profile
        profile = UserProfile.objects.filter(user=non_premium_user).first()
        self.assertIsNotNone(profile)
        self.assertFalse(profile.is_premium)

    def test_seed_demo_data_creates_demo_user_with_data(self):
        """Test: demo_user has students, contracts, lessons, and blocked times."""
        call_command("seed_demo_data", "--clear")

        non_premium_user = User.objects.get(username="demo_user")
        students = Student.objects.filter(user=non_premium_user)
        self.assertGreaterEqual(students.count(), 2, "demo_user should have at least 2 students")

        contracts = Contract.objects.filter(student__user=non_premium_user)
        self.assertGreaterEqual(contracts.count(), 2, "demo_user should have at least 2 contracts")

        lessons = Lesson.objects.filter(contract__student__user=non_premium_user)
        self.assertGreaterEqual(lessons.count(), 3, "demo_user should have at least 3 lessons")

        blocked_times = BlockedTime.objects.filter(user=non_premium_user)
        self.assertGreaterEqual(
            blocked_times.count(), 1, "demo_user should have at least 1 blocked time"
        )

    def test_seed_demo_data_week_view_loads_without_errors(self):
        """Test: Week view loads without errors with seed data."""
        from django.contrib.auth.models import User
        from django.test import Client

        call_command("seed_demo_data", "--clear")

        # Login as premium user
        premium_user = User.objects.get(username="demo_premium")
        client = Client()
        client.force_login(premium_user)

        # Try to load week view
        response = client.get("/lessons/week/")
        self.assertEqual(response.status_code, 200)
