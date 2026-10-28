
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Document

User = get_user_model()


class DocumentRoleTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username="student1",
            password="StudentPass123!",
        )

        self.admin = User.objects.create_user(
            username="admin1",
            password="AdminPass123!",
            is_staff=True,
            is_superuser=True,
        )

    def test_student_can_log_in(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "student1",
                "password": "StudentPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("submit_document"),
            fetch_redirect_response=False,
        )

    def test_student_cannot_access_admin(self):
        self.client.force_login(self.student)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_student_cannot_log_in_through_admin_login(self):
        response = self.client.post(
            "/admin/login/",
            {
                "username": "student1",
                "password": "StudentPass123!",
                "next": "/admin/",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_cannot_submit_documents(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("submit_document"))

        self.assertEqual(response.status_code, 403)

    def test_student_can_open_submission_page(self):
        self.client.force_login(self.student)

        response = self.client.get(reverse("submit_document"))

        self.assertEqual(response.status_code, 200)

    def test_student_submission_starts_as_pending(self):
        self.client.force_login(self.student)

        uploaded_file = SimpleUploadedFile(
            "student_id.txt",
            b"Test document content",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("submit_document"),
            {
                "document_type": "student_id",
                "file": uploaded_file,
            },
        )

        self.assertRedirects(
            response,
            reverse("submit_document"),
            fetch_redirect_response=False,
        )

        document = Document.objects.get(student=self.student)

        self.assertEqual(document.status, "pending")
        self.assertIsNone(document.reviewed_by_id)

    def create_pending_document(self):
        uploaded_file = SimpleUploadedFile(
            "student_id.txt",
            b"Test document content",
            content_type="text/plain",
        )

        return Document.objects.create(
            student=self.student,
            document_type="student_id",
            file=uploaded_file,
            status="pending",
        )

    def test_admin_cannot_add_documents_in_admin(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            "/admin/documents/document/add/"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_verify_document(self):
        document = self.create_pending_document()
        self.client.force_login(self.admin)

        response = self.client.post(
            f"/admin/documents/document/{document.id}/change/",
            {
                "status": "verified",
                "rejection_reason": "",
                "_save": "Save",
            },
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
            {
                "status": "rejected",
                "rejection_reason": "",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)

        document.refresh_from_db()

        self.assertEqual(document.status, "pending")
        self.assertIsNone(document.reviewed_by_id)
