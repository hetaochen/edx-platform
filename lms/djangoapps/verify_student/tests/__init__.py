from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from django.db import DEFAULT_DB_ALIAS
from django.test import TestCase
from django.utils.timezone import now
from lms.djangoapps.verify_student.models import SoftwareSecurePhotoVerification
from student.tests.factories import UserFactory

from django.conf import settings


class TestVerificationBase(TestCase):
    """
    Common tests across all types of Verifications (e.g., SoftwareSecurePhotoVerification, SSOVerification)
    """

    @contextmanager
    def immediate_on_commit(self, using=None):
        """
        Context manager executing transaction.on_commit() hooks immediately as
        if the connection was in auto-commit mode. This is required when
        using a subclass of django.test.TestCase as all tests are wrapped in
        a transaction that never gets committed.
        """
        immediate_using = DEFAULT_DB_ALIAS if using is None else using

        def on_commit(func, using=None):
            using = DEFAULT_DB_ALIAS if using is None else using
            if using == immediate_using:
                func()

        with mock.patch('django.db.transaction.on_commit', side_effect=on_commit) as patch:
            yield patch

    def verification_active_at_datetime(self, attempt):
        """
        Tests to ensure the Verification is active or inactive at the appropriate datetimes.
        """
        # Not active before the created date
        before = attempt.created_at - timedelta(seconds=1)
        self.assertFalse(attempt.active_at_datetime(before))

        # Active immediately after created date
        after_created = attempt.created_at + timedelta(seconds=1)
        self.assertTrue(attempt.active_at_datetime(after_created))

        # Active immediately before expiration date
        expiration = attempt.created_at + timedelta(days=settings.VERIFY_STUDENT["DAYS_GOOD_FOR"])
        before_expiration = expiration - timedelta(seconds=1)
        self.assertTrue(attempt.active_at_datetime(before_expiration))

        # Not active after the expiration date
        attempt.created_at = attempt.created_at - timedelta(days=settings.VERIFY_STUDENT["DAYS_GOOD_FOR"])
        attempt.save()
        self.assertFalse(attempt.active_at_datetime(now() + timedelta(days=1)))

    def submit_attempt(self, attempt):
        with self.immediate_on_commit():
            attempt.submit()
        return attempt

    def create_and_submit_attempt(self):
        user = UserFactory.create()
        attempt = SoftwareSecurePhotoVerification.objects.create(user=user)
        attempt.mark_ready()
        return self.submit_attempt(attempt)

    def create_upload_and_submit_attempt(self):
        """Helper method to create a generic submission and send it."""
        user = UserFactory.create()
        attempt = SoftwareSecurePhotoVerification(user=user)
        user.profile.name = u"Rust\u01B4"

        attempt.upload_face_image("Just pretend this is image data")
        attempt.upload_photo_id_image("Hey, we're a photo ID")
        attempt.mark_ready()
        return self.submit_attempt(attempt)
