from unittest import skip

from django.contrib.auth.models import User
from django.test import TestCase

from apps.lessons.models import Lesson
from apps.students.models import Student


@skip("Requires demo_data.json fixture not available")
class DemoFixturesLoadTest(TestCase):
    fixtures = ["demo_data.json"]

    def test_demo_users_and_lessons_exist(self):
        self.assertTrue(User.objects.filter(username="demo_premium").exists())
        self.assertTrue(User.objects.filter(username="demo_user").exists())
        self.assertGreaterEqual(Student.objects.count(), 3)
        self.assertGreaterEqual(Lesson.objects.count(), 3)

    def test_status_variety_present(self):
        self.assertTrue(Lesson.objects.filter(status="planned").exists())
        self.assertTrue(Lesson.objects.filter(status="taught").exists())
