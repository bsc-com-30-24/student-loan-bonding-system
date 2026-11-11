import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate

from authentication.models import UserProfile

from .api_views import StudentNotificationMarkReadAPIView
from .models import Document, Notification

User = get_user_model()

PDF = b"%PDF-1.4\n%test document\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32

# Uploaded test files go to a throw-away folder, never to the real MEDIA_ROOT.
TEST_MEDIA = tempfile.mkdtemp(prefix="slbs-test-media-")


def tearDownModule():
    shutil.rmtree(TEST_MEDIA, ignore_errors=True)


def pdf_file(name="student_id.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def make_user(username, role=None, **extra):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StudentPass123!",
        **extra,
    )
    if role:
        UserProfile.objects.create(user=user, role=role)
    return user


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class DocumentRoleTests(TestCase):
    """Browser pages: login redirect, submission form and the Django admin."""

    def setUp(self):
        self.student = make_user("student1")  # no profile -> student by default
        self.admin = make_user("admin1", is_staff=True, is_superuser=True)

    def create_pending_document(self):
        return Document.objects.create(
            student=self.student,
            document_type="student_id",
            file=pdf_file(),
            status="pending",
        )

    def test_student_can_log_in(self):
        response = self.client.post(
            reverse("login"),
            {"username": "student1", "password": "StudentPass123!"},
        )
        self.assertRedirects(
            response, reverse("submit_document"), fetch_redirect_response=False
        )

    def test_student_cannot_access_admin(self):
        self.client.force_login(self.student)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_student_cannot_log_in_through_admin_login(self):
        response = self.client.post(
            "/admin/login/",
            {"username": "student1", "password": "StudentPass123!", "next": "/admin/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_cannot_submit_documents(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("submit_document"))
        self.assertEqual(response.status_code, 403)

    def test_other_roles_cannot_submit_documents(self):
        for role in (UserProfile.Role.LOAN_BOARD_OFFICER, UserProfile.Role.EMPLOYER):
            user = make_user(f"user_{role}", role)
            self.client.force_login(user)
            response = self.client.get(reverse("submit_document"))
            self.assertEqual(response.status_code, 403, role)

    def test_student_can_open_submission_page(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("submit_document"))
        self.assertEqual(response.status_code, 200)

    def test_student_submission_starts_as_pending(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("submit_document"),
            {"document_type": "student_id", "file": pdf_file()},
        )
        self.assertRedirects(
            response, reverse("submit_document"), fetch_redirect_response=False
        )
        document = Document.objects.get(student=self.student)
        self.assertEqual(document.status, "pending")
        self.assertIsNone(document.reviewed_by_id)

    def test_submission_form_rejects_bad_files_and_types(self):
        self.client.force_login(self.student)
        bad_uploads = [
            {"document_type": "student_id",
             "file": SimpleUploadedFile("page.html", b"<script>alert(1)</script>")},
            {"document_type": "student_id",
             "file": SimpleUploadedFile("fake.pdf", b"not really a pdf")},
            {"document_type": "not_a_type", "file": pdf_file()},
            {"document_type": "student_id"},
        ]
        for payload in bad_uploads:
            self.client.post(reverse("submit_document"), payload)
        self.assertEqual(Document.objects.count(), 0)

    def test_admin_cannot_add_documents_in_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/documents/document/add/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_verify_document(self):
        document = self.create_pending_document()
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/admin/documents/document/{document.id}/change/",
            {"status": "verified", "rejection_reason": "", "_save": "Save"},
        )
        self.assertEqual(response.status_code, 302)
        document.refresh_from_db()
        self.assertEqual(document.status, "verified")
        self.assertEqual(document.reviewed_by, self.admin)
        self.assertIsNotNone(document.reviewed_at)

    def test_admin_cannot_reject_without_reason(self):
        document = self.create_pending_document()
        self.client.force_login(self.admin)
        response = self.client.post(
            f"/admin/documents/document/{document.id}/change/",
            {"status": "rejected", "rejection_reason": "", "_save": "Save"},
        )
        self.assertEqual(response.status_code, 200)
        document.refresh_from_db()
        self.assertEqual(document.status, "pending")
        self.assertIsNone(document.reviewed_by_id)

    def test_admin_rejection_notifies_student(self):
        document = self.create_pending_document()
        self.client.force_login(self.admin)
        self.client.post(
            f"/admin/documents/document/{document.id}/change/",
            {"status": "rejected", "rejection_reason": "Blurry scan", "_save": "Save"},
        )
        self.assertEqual(Notification.objects.filter(student=self.student).count(), 1)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class DocumentApiTests(APITestCase):
    """The documents API, protected by the authentication app's roles."""

    def setUp(self):
        cache.clear()  # reset throttle counters used by the register endpoint
        self.student = make_user("student1", UserProfile.Role.STUDENT)
        self.other_student = make_user("student2", UserProfile.Role.STUDENT)
        self.university_admin = make_user("uni_admin", UserProfile.Role.UNIVERSITY_ADMIN)
        self.staff_admin = make_user("admin1", is_staff=True, is_superuser=True)
        self.officer = make_user("officer", UserProfile.Role.LOAN_BOARD_OFFICER)
        self.employer = make_user("employer", UserProfile.Role.EMPLOYER)

        self.my_docs = reverse("student_documents_api")
        self.my_notes = reverse("student_notifications_api")
        self.admin_list = reverse("admin_documents_api")

    def make_document(self, student=None, name="id.pdf", content=PDF, **extra):
        return Document.objects.create(
            student=student or self.student,
            document_type="student_id",
            file=SimpleUploadedFile(name, content),
            **extra,
        )

    def preview_url(self, document):
        return reverse("admin_document_preview_api", kwargs={"pk": document.pk})

    def verify_url(self, document):
        return reverse("document_verification_api", kwargs={"pk": document.pk})

    # ---- authentication -------------------------------------------------

    def test_every_endpoint_requires_login(self):
        document = self.make_document()
        urls = [
            ("get", self.my_docs),
            ("post", self.my_docs),
            ("get", self.my_notes),
            ("get", self.admin_list),
            ("get", self.preview_url(document)),
            ("patch", self.verify_url(document)),
        ]
        for method, url in urls:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 401, (method, url))

    def test_full_flow_with_real_jwt_login(self):
        register = self.client.post(
            reverse("register"),
            {
                "username": "new_student",
                "email": "new@example.com",
                "student_registration_number": "BSCS/2025/777",
                "password": "Unique-strong-password-2026!",
                "password_confirmation": "Unique-strong-password-2026!",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201)

        token = self.client.post(
            reverse("token_obtain_pair"),
            {"username": "new_student", "password": "Unique-strong-password-2026!"},
            format="json",
        )
        self.assertEqual(token.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")

        upload = self.client.post(
            self.my_docs,
            {"document_type": "national_id", "file": pdf_file("nid.pdf")},
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201)
        self.assertEqual(upload.data["status"], "pending")

        listing = self.client.get(self.my_docs)
        self.assertEqual([d["id"] for d in listing.data], [upload.data["id"]])

    # ---- student endpoints ---------------------------------------------

    def test_student_upload_starts_pending_and_cannot_set_status(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            self.my_docs,
            {"document_type": "student_id", "file": pdf_file(), "status": "verified"},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)
        document = Document.objects.get(pk=response.data["id"])
        self.assertEqual(document.student, self.student)
        self.assertEqual(document.status, "pending")

    def test_png_upload_is_accepted(self):
        self.client.force_authenticate(self.student)
        response = self.client.post(
            self.my_docs,
            {"document_type": "guarantor_id",
             "file": SimpleUploadedFile("g.png", PNG, content_type="image/png")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 201)

    def test_bad_uploads_are_rejected(self):
        self.client.force_authenticate(self.student)
        too_big = b"%PDF" + b"0" * (5 * 1024 * 1024)
        bad_payloads = [
            {"document_type": "student_id",
             "file": SimpleUploadedFile("page.html", b"<script>alert(1)</script>")},
            {"document_type": "student_id",
             "file": SimpleUploadedFile("run.exe", b"MZ....")},
            {"document_type": "student_id",
             "file": SimpleUploadedFile("fake.pdf", b"plain text, not a pdf")},
            {"document_type": "student_id", "file": pdf_file("big.pdf", too_big)},
            {"document_type": "not_a_type", "file": pdf_file()},
            {"document_type": "student_id"},
            {"file": pdf_file()},
        ]
        for payload in bad_payloads:
            response = self.client.post(self.my_docs, payload, format="multipart")
            self.assertEqual(response.status_code, 400, list(payload))
        self.assertEqual(Document.objects.count(), 0)

    def test_student_sees_only_own_documents_and_notifications(self):
        mine = self.make_document(self.student)
        self.make_document(self.other_student)
        Notification.objects.create(student=self.other_student,
                                    document=mine, message="not for me")
        self.client.force_authenticate(self.student)
        self.assertEqual(
            [d["id"] for d in self.client.get(self.my_docs).data], [mine.id]
        )
        self.assertEqual(self.client.get(self.my_notes).data, [])

    def test_only_students_can_use_student_endpoints(self):
        for user in (self.university_admin, self.staff_admin, self.officer, self.employer):
            self.client.force_authenticate(user)
            for response in (
                self.client.get(self.my_docs),
                self.client.post(
                    self.my_docs,
                    {"document_type": "student_id", "file": pdf_file()},
                    format="multipart",
                ),
                self.client.get(self.my_notes),
            ):
                self.assertEqual(response.status_code, 403, user.username)
        self.assertEqual(Document.objects.count(), 0)

    # ---- reviewer endpoints --------------------------------------------

    def test_only_reviewers_can_use_admin_endpoints(self):
        document = self.make_document()
        for user in (self.student, self.officer, self.employer):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.admin_list).status_code, 403)
            self.assertEqual(self.client.get(self.preview_url(document)).status_code, 403)
            response = self.client.patch(
                self.verify_url(document), {"status": "verified"}, format="json"
            )
            self.assertEqual(response.status_code, 403, user.username)
        document.refresh_from_db()
        self.assertEqual(document.status, "pending")

    def test_reviewers_can_list_all_documents_with_preview_url(self):
        first = self.make_document(self.student)
        self.make_document(self.other_student)
        for user in (self.university_admin, self.staff_admin):
            self.client.force_authenticate(user)
            response = self.client.get(self.admin_list)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 2)
            row = next(r for r in response.data if r["id"] == first.id)
            self.assertEqual(row["student_username"], "student1")
            self.assertTrue(row["preview_url"].endswith(f"/{first.id}/preview/"))

    def test_preview_serves_pdf_inline_and_forces_download_for_other_types(self):
        pdf_doc = self.make_document(name="id.pdf")
        text_doc = self.make_document(name="notes.txt", content=b"hello")
        self.client.force_authenticate(self.university_admin)

        response = self.client.get(self.preview_url(pdf_doc))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("inline"))
        self.assertEqual(b"".join(response.streaming_content), PDF)

        response = self.client.get(self.preview_url(text_doc))
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))

        self.assertEqual(self.client.get("/documents/api/admin/documents/9999/preview/").status_code, 404)

    def test_verify_records_reviewer_and_clears_reason(self):
        document = self.make_document(status="rejected", rejection_reason="old reason")
        self.client.force_authenticate(self.university_admin)
        response = self.client.patch(
            self.verify_url(document), {"status": "verified"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reviewed_by"], "uni_admin")
        document.refresh_from_db()
        self.assertEqual(document.status, "verified")
        self.assertEqual(document.rejection_reason, "")
        self.assertEqual(document.reviewed_by, self.university_admin)
        self.assertIsNotNone(document.reviewed_at)

    def test_invalid_review_requests_return_400_never_500(self):
        document = self.make_document()
        self.client.force_authenticate(self.university_admin)
        bad_bodies = [
            {"status": "approved"},
            {},
            {"status": "rejected"},
            {"status": "rejected", "rejection_reason": "   "},
            {"status": "rejected", "rejection_reason": None},
            {"status": "rejected", "rejection_reason": 123},
            ["status", "rejected"],
        ]
        for body in bad_bodies:
            response = self.client.patch(self.verify_url(document), body, format="json")
            self.assertEqual(response.status_code, 400, body)
        document.refresh_from_db()
        self.assertEqual(document.status, "pending")
        self.assertEqual(Notification.objects.count(), 0)

    def test_unknown_document_returns_404(self):
        self.client.force_authenticate(self.university_admin)
        response = self.client.patch(
            reverse("document_verification_api", kwargs={"pk": 9999}),
            {"status": "verified"}, format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_api_rejection_notifies_student_once(self):
        document = self.make_document()
        self.client.force_authenticate(self.university_admin)
        body = {"status": "rejected", "rejection_reason": "Photo is unreadable"}

        response = self.client.patch(self.verify_url(document), body, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.patch(self.verify_url(document), body, format="json")  # repeat

        self.assertEqual(Notification.objects.count(), 1)  # not duplicated
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student1@example.com"])

        self.client.force_authenticate(self.student)
        notes = self.client.get(self.my_notes).data
        self.assertEqual(len(notes), 1)
        self.assertIn("Photo is unreadable", notes[0]["message"])
        self.assertEqual(notes[0]["document"], document.id)

        self.client.force_authenticate(self.other_student)
        self.assertEqual(self.client.get(self.my_notes).data, [])


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class NotificationMarkReadTests(APITestCase):
    """Calls the view directly, so the tests do not depend on the URL name."""

    def setUp(self):
        self.student = make_user("student1", UserProfile.Role.STUDENT)
        self.other_student = make_user("student2", UserProfile.Role.STUDENT)
        self.officer = make_user("officer", UserProfile.Role.LOAN_BOARD_OFFICER)
        document = Document.objects.create(
            student=self.student, document_type="student_id", file=pdf_file()
        )
        self.note = Notification.objects.create(
            student=self.student, document=document, message="Rejected"
        )
        self.view = StudentNotificationMarkReadAPIView.as_view()
        self.factory = APIRequestFactory()

    def call(self, method, user=None, pk=None):
        request = getattr(self.factory, method)("/read/")
        if user:
            force_authenticate(request, user=user)
        return self.view(request, pk=pk or self.note.pk)

    def test_student_marks_own_notification_read_with_patch_or_post(self):
        for method in ("patch", "post"):
            Notification.objects.filter(pk=self.note.pk).update(is_read=False)
            response = self.call(method, self.student)
            self.assertEqual(response.status_code, 200, method)
            self.assertTrue(response.data["is_read"])
            self.note.refresh_from_db()
            self.assertTrue(self.note.is_read)

    def test_marking_twice_is_harmless(self):
        self.assertEqual(self.call("patch", self.student).status_code, 200)
        self.assertEqual(self.call("patch", self.student).status_code, 200)

    def test_other_students_notification_is_404(self):
        self.assertEqual(self.call("patch", self.other_student).status_code, 404)
        self.note.refresh_from_db()
        self.assertFalse(self.note.is_read)

    def test_unknown_notification_is_404(self):
        self.assertEqual(self.call("patch", self.student, pk=9999).status_code, 404)

    def test_non_students_and_anonymous_are_refused(self):
        self.assertEqual(self.call("patch", self.officer).status_code, 403)
        self.assertEqual(self.call("patch").status_code, 401)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class DocumentDownloadTests(APITestCase):
    """GET /api/<id>/download/: students get their own files, reviewers get any."""

    def setUp(self):
        self.student = make_user("student1", UserProfile.Role.STUDENT)
        self.other_student = make_user("student2", UserProfile.Role.STUDENT)
        self.university_admin = make_user("uni_admin", UserProfile.Role.UNIVERSITY_ADMIN)
        self.staff_admin = make_user("admin1", is_staff=True, is_superuser=True)
        self.officer = make_user("officer", UserProfile.Role.LOAN_BOARD_OFFICER)
        self.employer = make_user("employer", UserProfile.Role.EMPLOYER)
        self.document = Document.objects.create(
            student=self.student,
            document_type="student_id",
            file=SimpleUploadedFile("my_id.pdf", PDF),
        )

    def url(self, document=None):
        return reverse(
            "document_download_api", kwargs={"pk": (document or self.document).pk}
        )

    def test_student_downloads_own_document_as_attachment(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))
        self.assertIn("my_id", response["Content-Disposition"])
        self.assertEqual(b"".join(response.streaming_content), PDF)

    def test_student_cannot_download_someone_elses_document(self):
        self.client.force_authenticate(self.other_student)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_reviewers_can_download_any_document(self):
        for user in (self.university_admin, self.staff_admin):
            self.client.force_authenticate(user)
            response = self.client.get(self.url())
            self.assertEqual(response.status_code, 200, user.username)
            self.assertEqual(b"".join(response.streaming_content), PDF)

    def test_other_roles_and_anonymous_are_refused(self):
        for user in (self.officer, self.employer):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.url()).status_code, 403, user.username)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url()).status_code, 401)

    def test_unknown_document_is_404(self):
        self.client.force_authenticate(self.university_admin)
        response = self.client.get(
            reverse("document_download_api", kwargs={"pk": 9999})
        )
        self.assertEqual(response.status_code, 404)

    def test_non_pdf_or_image_downloads_as_generic_binary(self):
        text_doc = Document.objects.create(
            student=self.student,
            document_type="other_letter",
            file=SimpleUploadedFile("notes.txt", b"hello"),
        )
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url(text_doc))
        self.assertEqual(response["Content-Type"], "application/octet-stream")
        self.assertTrue(response["Content-Disposition"].startswith("attachment"))

    def test_missing_file_returns_404_with_error_message(self):
        no_file = Document.objects.create(
            student=self.student, document_type="affidavit", file=""
        )
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url(no_file))
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)

        os.remove(self.document.file.path)  # row exists, file gone from disk
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.data)

    def test_document_lists_include_a_working_download_url(self):
        self.client.force_authenticate(self.student)
        row = self.client.get(reverse("student_documents_api")).data[0]
        self.assertTrue(row["download_url"].endswith(f"/{self.document.id}/download/"))

        self.client.force_authenticate(self.university_admin)
        row = self.client.get(reverse("admin_documents_api")).data[0]
        self.assertTrue(row["download_url"].endswith(f"/{self.document.id}/download/"))
        self.assertEqual(self.client.get(row["download_url"]).status_code, 200)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class RawFileUrlIsNeverExposedTests(APITestCase):
    """Files must only be reachable through the protected download/preview endpoints."""

    def test_no_response_contains_the_raw_file_url(self):
        student = make_user("student1", UserProfile.Role.STUDENT)
        admin = make_user("uni_admin", UserProfile.Role.UNIVERSITY_ADMIN)

        self.client.force_authenticate(student)
        upload = self.client.post(
            reverse("student_documents_api"),
            {"document_type": "student_id", "file": pdf_file("secret_id.pdf")},
            format="multipart",
        )
        self.assertEqual(upload.status_code, 201)
        self.assertNotIn("file", upload.data)
        self.assertIn("download_url", upload.data)

        listing = self.client.get(reverse("student_documents_api"))
        self.assertNotIn("file", listing.data[0])
        self.assertNotIn("student_documents/", str(listing.data))

        self.client.force_authenticate(admin)
        rows = self.client.get(reverse("admin_documents_api"))
        self.assertNotIn("file", rows.data[0])
        self.assertNotIn("student_documents/", str(rows.data))
        self.assertIn("preview_url", rows.data[0])
        self.assertIn("download_url", rows.data[0])