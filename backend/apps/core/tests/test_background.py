"""run_in_background: nach dem Commit, in eigenem Thread, mit der Sprache der Anfrage."""

import threading

from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import translation

from apps.core.background import run_in_background


def _wait_for_background_threads():
    for thread in threading.enumerate():
        if thread.name.startswith("background: "):
            thread.join(5)


@override_settings(RUN_IN_BACKGROUND=True)
class BackgroundTest(TestCase):
    def test_runs_after_commit_in_another_thread_with_the_request_language(self):
        seen = {}

        def work(value, *, flag):
            seen.update(
                value=value,
                flag=flag,
                thread=threading.get_ident(),
                language=translation.get_language(),
            )

        with translation.override("en"), self.captureOnCommitCallbacks() as callbacks:
            run_in_background("Test", work, 42, flag=True)
            self.assertEqual(seen, {})  # noch nichts passiert

        self.assertEqual(len(callbacks), 1)
        callbacks[0]()
        _wait_for_background_threads()

        self.assertEqual(seen["value"], 42)
        self.assertTrue(seen["flag"])
        self.assertNotEqual(seen["thread"], threading.get_ident())
        self.assertEqual(seen["language"], "en")

    def test_nothing_runs_when_the_transaction_rolls_back(self):
        with self.captureOnCommitCallbacks() as callbacks:
            try:
                with transaction.atomic():
                    run_in_background("Test", lambda: None)
                    raise RuntimeError("zurückrollen")
            except RuntimeError:
                pass

        self.assertEqual(callbacks, [])

    def test_errors_are_logged_not_raised(self):
        def broken():
            raise ValueError("Mailserver weg")

        with self.assertLogs("apps.core.background", level="ERROR") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                run_in_background("Kaputte Mail", broken)
            _wait_for_background_threads()

        self.assertIn("Kaputte Mail", logs.output[0])


@override_settings(RUN_IN_BACKGROUND=False)
class SynchronousModeTest(TestCase):
    def test_runs_immediately(self):
        seen = []
        run_in_background("Test", seen.append, 1)
        self.assertEqual(seen, [1])

    def test_errors_are_logged_not_raised(self):
        def broken():
            raise ValueError("Mailserver weg")

        with self.assertLogs("apps.core.background", level="ERROR"):
            run_in_background("Kaputte Mail", broken)
