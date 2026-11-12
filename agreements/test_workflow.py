import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from decimal import Decimal

from agreements.models import Agreement
from authentication.models import LoanApplication, UserProfile
from bonds.models import Bond
from documents.models import Notification
from documents.services import COMPULSORY_DOCUMENT_TYPES

User = get_user_model()

TEST_MEDIA_ROOT = tempfile.mkdtemp()


def make_user(username, role, registration_number=None):
    """
    ASSUMPTION: UserProfile has a `user` link, a `role` field and a
    `student_registration_number` field. If your model differs, this is the
    only place to adjust.
    """
    user = User.objects.create_user(username=username, password="Pass12345!")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = role
    if registration_number:
        profile.student_registration_number = registration_number
    profile.save()
    return user


def signed_pdf(name="signed.pdf"):
    return SimpleUploadedFile(
        name, b"%PDF-1.4 signed copy", content_type="application/pdf"
    )


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class WorkflowIntegrationTests(APITestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.student = make_user(
            "student1", UserProfile.Role.STUDENT, "REG-001"
        )
        self.other_student = make_user(
            "student2", UserProfile.Role.STUDENT, "REG-002"
        )
        self.admin = make_user("admin1", UserProfile.Role.UNIVERSITY_ADMIN)
        self.officer = make_user(
            "officer1", UserProfile.Role.LOAN_BOARD_OFFICER
        )
        LoanApplication.objects.create(
            owner=self.student,
            tuition_amount=Decimal("800.00"),
            upkeep_amount=Decimal("200.00"),
        )
        LoanApplication.objects.create(
            owner=self.other_student,
            tuition_amount=Decimal("100.00"),
            upkeep_amount=Decimal("50.00"),
        )

    # ---------- helpers ----------

    def upload(self, doc_type, user=None):
        self.client.force_authenticate(user or self.student)
        response = self.client.post(
            reverse("student_documents_api"),
            {
                "document_type": doc_type,
                "file": SimpleUploadedFile(
                    f"{doc_type}.pdf",
                    b"%PDF-1.4 test file",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data["id"]

    def review(self, doc_id, new_status="verified", reason=""):
        self.client.force_authenticate(self.admin)
        return self.client.patch(
            reverse("document_verification_api", kwargs={"pk": doc_id}),
            {"status": new_status, "rejection_reason": reason},
            format="json",
        )

    def upload_and_verify_all(self, user=None):
        """Returns the response of the LAST verification."""
        response = None
        for doc_type in COMPULSORY_DOCUMENT_TYPES:
            doc_id = self.upload(doc_type, user)
            response = self.review(doc_id)
            self.assertEqual(response.status_code, 200, response.data)
        return response

    def approve_bond(self, bond_id):
        self.client.force_authenticate(self.admin)
        return self.client.patch(
            reverse("bond-status-update", kwargs={"pk": bond_id}),
            {"status": "approved"},
            format="json",
        )

    # ---------- tests ----------

    def test_full_workflow(self):
        # 1-2. Student submits, admin verifies. The bond appears only
        # after the last compulsory document is verified.
        last = None
        for index, doc_type in enumerate(COMPULSORY_DOCUMENT_TYPES):
            last = self.review(self.upload(doc_type))
            self.assertEqual(last.status_code, 200, last.data)
            is_last = index == len(COMPULSORY_DOCUMENT_TYPES) - 1
            self.assertEqual(last.data["bond_generated"], is_last)
            self.assertEqual(Bond.objects.count(), 1 if is_last else 0)

        # 3. Exactly one pending bond, reported in the response.
        bond = Bond.objects.get()
        self.assertEqual(bond.student, self.student)
        self.assertEqual(bond.status, "pending")
        self.assertEqual(last.data["bond_id"], bond.id)

        self.assertTrue(last.data["agreement_generated"])
        self.assertEqual(
            Notification.objects.filter(student=self.student).count(),
            1,
        )

        # The student sees the bond; another student does not.
        self.client.force_authenticate(self.student)
        listing = self.client.get(reverse("bond-list-create"))
        self.assertEqual([b["id"] for b in listing.data], [bond.id])
        self.client.force_authenticate(self.other_student)
        self.assertEqual(
            self.client.get(reverse("bond-list-create")).data, []
        )

        agreement = Agreement.objects.get()
        self.assertEqual(agreement.bond_id, bond.id)
        self.assertEqual(agreement.total_amount, Decimal("1000.00"))
        agreement_number = str(agreement.agreement_number)

        # A second generate call does not replace the agreement.
        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.post(reverse("agreement-generate")).status_code, 400
        )
        self.assertEqual(Agreement.objects.count(), 1)

        # The bond is approved after the agreement exists.
        response = self.approve_bond(bond.id)
        self.assertEqual(response.status_code, 200, response.data)

        sign_url = reverse(
            "agreement-sign", kwargs={"agreement_number": agreement_number}
        )
        countersign_url = reverse(
            "agreement-countersign",
            kwargs={"agreement_number": agreement_number},
        )

        download_url = reverse(
            "agreement-download",
            kwargs={"agreement_number": agreement_number},
        )

        def upload(url, user, file=None):
            self.client.force_authenticate(user)
            data = {"signed_document": file} if file else {}
            return self.client.post(url, data, format="multipart")

        # Countersigning before the student signs is refused.
        self.assertEqual(
            upload(countersign_url, self.officer, signed_pdf()).status_code,
            400,
        )

        # Another student cannot sign it.
        self.assertEqual(
            upload(sign_url, self.other_student, signed_pdf()).status_code,
            403,
        )

        # The student downloads the original; no signed copy exists yet.
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(download_url).status_code, 200)
        self.assertEqual(
            self.client.get(
                download_url, {"version": "student_signed"}
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(download_url, {"version": "bogus"}).status_code,
            400,
        )

        # A missing file or a non-PDF upload is refused.
        self.assertEqual(upload(sign_url, self.student).status_code, 400)
        not_pdf = SimpleUploadedFile(
            "signed.txt", b"not a pdf", content_type="text/plain"
        )
        self.assertEqual(
            upload(sign_url, self.student, not_pdf).status_code, 400
        )
        fake_pdf = SimpleUploadedFile(
            "signed.pdf", b"this is not really a pdf",
            content_type="application/pdf",
        )
        self.assertEqual(
            upload(sign_url, self.student, fake_pdf).status_code, 400
        )

        # 6. The owner uploads the signed copy.
        response = upload(sign_url, self.student, signed_pdf())
        self.assertEqual(response.status_code, 200, response.data)
        agreement = Agreement.objects.get()
        self.assertEqual(agreement.status, Agreement.Status.SIGNED)
        self.assertTrue(agreement.student_signed_document)
        self.assertEqual(len(agreement.student_signed_document_sha256), 64)

        # A second upload is refused.
        self.assertEqual(
            upload(sign_url, self.student, signed_pdf()).status_code, 400
        )

        # Only the Loan Board Officer may countersign.
        for user in (self.student, self.admin):
            self.assertEqual(
                upload(countersign_url, user, signed_pdf()).status_code, 403
            )

        # The officer downloads the student-signed copy, signs it and
        # uploads the final version.
        self.client.force_authenticate(self.officer)
        self.assertEqual(
            self.client.get(
                download_url, {"version": "student_signed"}
            ).status_code,
            200,
        )
        self.assertEqual(
            upload(countersign_url, self.officer).status_code, 400
        )

        # 7. The officer uploads the countersigned copy.
        response = upload(countersign_url, self.officer, signed_pdf())
        self.assertEqual(response.status_code, 200, response.data)
        agreement.refresh_from_db()
        self.assertEqual(agreement.status, Agreement.Status.COUNTERSIGNED)
        self.assertTrue(agreement.countersigned_document)
        self.assertEqual(agreement.countersigned_by, self.officer)

        # The final copy can be downloaded by everyone involved, but not
        # by an unrelated student.
        for user in (self.student, self.officer, self.admin):
            self.client.force_authenticate(user)
            self.assertEqual(
                self.client.get(
                    download_url, {"version": "countersigned"}
                ).status_code,
                200,
            )
        self.client.force_authenticate(self.other_student)
        self.assertEqual(
            self.client.get(
                download_url, {"version": "countersigned"}
            ).status_code,
            403,
        )

    def test_rejected_document_blocks_the_bond(self):
        for doc_type in COMPULSORY_DOCUMENT_TYPES[:-1]:
            self.review(self.upload(doc_type))

        rejected = self.review(
            self.upload(COMPULSORY_DOCUMENT_TYPES[-1]),
            "rejected",
            "Photo is blurry",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(Bond.objects.count(), 0)

        # Re-uploading and verifying a good copy completes the set.
        response = self.review(self.upload(COMPULSORY_DOCUMENT_TYPES[-1]))
        self.assertTrue(response.data["bond_generated"])
        self.assertEqual(Bond.objects.count(), 1)

    def test_no_duplicate_bond(self):
        self.upload_and_verify_all()
        self.assertEqual(Bond.objects.count(), 1)

        # Re-verifying more copies of compulsory documents adds nothing.
        for doc_type in COMPULSORY_DOCUMENT_TYPES:
            response = self.review(self.upload(doc_type))
            self.assertFalse(response.data["bond_generated"])

        self.assertEqual(Bond.objects.filter(student=self.student).count(), 1)

    def test_bonds_are_per_student(self):
        self.upload_and_verify_all(self.student)
        self.upload_and_verify_all(self.other_student)
        self.assertEqual(Bond.objects.count(), 2)

    def test_roles_are_enforced_on_documents(self):
        doc_id = self.upload(COMPULSORY_DOCUMENT_TYPES[0])
        verify_url = reverse("document_verification_api", kwargs={"pk": doc_id})

        for user in (self.student, self.officer):
            self.client.force_authenticate(user)
            response = self.client.patch(
                verify_url, {"status": "verified"}, format="json"
            )
            self.assertEqual(response.status_code, 403)

        for user in (self.admin, self.officer):
            self.client.force_authenticate(user)
            response = self.client.get(reverse("student_documents_api"))
            self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(None)
        response = self.client.get(reverse("student_documents_api"))
        self.assertEqual(response.status_code, 401)

    def test_bond_review_is_admin_only(self):
        self.upload_and_verify_all()
        bond = Bond.objects.get()

        for user in (self.student, self.officer):
            self.client.force_authenticate(user)
            response = self.client.patch(
                reverse("bond-status-update", kwargs={"pk": bond.id}),
                {"status": "approved"},
                format="json",
            )
            self.assertEqual(response.status_code, 403)