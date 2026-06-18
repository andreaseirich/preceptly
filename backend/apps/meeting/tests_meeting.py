import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.lessons.models import Session, SessionDocument
from apps.meeting.models import MeetingRoom

User = get_user_model()


def make_user(**kwargs):
    defaults = {"username": f"u{uuid.uuid4().hex[:8]}", "password": "pw"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_contract(user):
    from apps.contracts.models import Contract

    return Contract.objects.create(user=user, first_name="Test", last_name="Student")


def make_session(contract):
    from datetime import date, time

    return Session.objects.create(
        contract=contract, date=date(2025, 1, 15), start_time=time(14, 0), duration_minutes=60
    )


def make_room(lesson, *, is_active=False):
    return MeetingRoom.objects.create(lesson=lesson, is_active=is_active)


class StartMeetingViewTest(TestCase):
    def setUp(self):
        self.tutor = make_user()
        self.contract = make_contract(self.tutor)
        self.lesson = make_session(self.contract)

    def test_tutor_can_start_meeting(self):
        self.client.force_login(self.tutor)
        url = reverse("meeting:start", kwargs={"lesson_pk": self.lesson.pk})
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302])
        self.assertTrue(MeetingRoom.objects.filter(lesson=self.lesson, is_active=True).exists())

    def test_non_tutor_cannot_start_meeting(self):
        other = make_user()
        self.client.force_login(other)
        url = reverse("meeting:start", kwargs={"lesson_pk": self.lesson.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class EndMeetingViewTest(TestCase):
    def setUp(self):
        self.tutor = make_user()
        self.contract = make_contract(self.tutor)
        self.lesson = make_session(self.contract)
        self.room = make_room(self.lesson, is_active=True)

    def test_end_meeting_deactivates_room(self):
        self.client.force_login(self.tutor)
        url = reverse("meeting:end", kwargs={"token": str(self.room.token)})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.room.refresh_from_db()
        self.assertFalse(self.room.is_active)

    def test_end_meeting_rotates_token(self):
        self.client.force_login(self.tutor)
        old_token = self.room.token
        url = reverse("meeting:end", kwargs={"token": str(old_token)})
        self.client.post(url)
        self.room.refresh_from_db()
        self.assertNotEqual(self.room.token, old_token)


class MeetingRoomViewGuestTest(TestCase):
    def setUp(self):
        self.tutor = make_user()
        self.contract = make_contract(self.tutor)
        self.lesson = make_session(self.contract)
        self.room = make_room(self.lesson, is_active=True)

    def test_valid_token_grants_access(self):
        self.client.force_login(self.tutor)
        url = reverse("meeting:room", kwargs={"token": str(self.room.token)})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_invalid_token_returns_404(self):
        url = reverse("meeting:room", kwargs={"token": str(uuid.uuid4())})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_inactive_room_returns_404(self):
        self.room.is_active = False
        self.room.save()
        self.client.force_login(self.tutor)
        url = reverse("meeting:room", kwargs={"token": str(self.room.token)})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class MeetingDocumentUploadViewTest(TestCase):
    def setUp(self):
        self.tutor = make_user()
        self.contract = make_contract(self.tutor)
        self.lesson = make_session(self.contract)
        self.room = make_room(self.lesson, is_active=True)

    def test_tutor_can_upload_in_active_meeting(self):
        self.client.force_login(self.tutor)
        url = reverse("meeting:upload", kwargs={"token": str(self.room.token)})
        upload = SimpleUploadedFile("doc.pdf", b"content", content_type="application/pdf")
        response = self.client.post(url, {"file": upload})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SessionDocument.objects.filter(session=self.lesson).exists())

    def test_upload_fails_for_inactive_room(self):
        inactive_room = make_room(make_session(self.contract), is_active=False)
        self.client.force_login(self.tutor)
        url = reverse("meeting:upload", kwargs={"token": str(inactive_room.token)})
        upload = SimpleUploadedFile("doc.pdf", b"content", content_type="application/pdf")
        response = self.client.post(url, {"file": upload})
        self.assertEqual(response.status_code, 404)


class MeetingRoomModelTest(TestCase):
    def setUp(self):
        self.tutor = make_user()
        self.contract = make_contract(self.tutor)

    def test_token_is_uuid(self):
        lesson = make_session(self.contract)
        room = MeetingRoom.objects.create(lesson=lesson)
        self.assertIsInstance(room.token, uuid.UUID)

    def test_token_is_unique(self):
        lesson1 = make_session(self.contract)
        lesson2 = make_session(self.contract)
        room1 = MeetingRoom.objects.create(lesson=lesson1)
        room2 = MeetingRoom.objects.create(lesson=lesson2)
        self.assertNotEqual(room1.token, room2.token)
