import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from decimal import Decimal

from agreements.models import Agreement
from authentication.models import LoanApplication, StudentDetail, UserProfile
from bonds.academic import get_or_create_academic_year
from bonds.models import Bond

from .models import Document, Notification
from .services import COMPULSORY_DOCUMENT_TYPES

User = get_user_model()


def signed_pdf(name="signed.pdf"):
    return SimpleUploadedFile(
        name, b"%PDF-1.4 signed copy", content_type="application/pdf"
    )

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
        StudentDetail.objects.create(
            user=self.student,
            full_name="Aku Banda",
            programme="BSc Computer Science",
            year_of_study=2,
            phone_number="+265999123456",
        )
        self.application = LoanApplication.objects.create(
            owner=self.student,
            tuition_amount=Decimal("450000.00"),
            upkeep_amount=Decimal("50000.00"),
        )
        LoanApplication.objects.create(
            owner=self.other_student,
            tuition_amount=Decimal("100.00"),
            upkeep_amount=Decimal("50.00"),
        )

    # ---------- helpers ----------

    def upload(self, doc_type, user=None, loan_application=None):
        self.client.force_authenticate(user or self.student)
        payload = {
            "document_type": doc_type,
            "file": SimpleUploadedFile(
                f"{doc_type}.pdf",
                b"%PDF-1.4 test file",
                content_type="application/pdf",
            ),
        }
        if loan_application is not None:
            payload["loan_application"] = loan_application
        response = self.client.post(
            reverse("student_documents_api"),
            payload,
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

        # The agreement is generated with the bond and stays pending.
        self.assertTrue(last.data["agreement_generated"])
        agreement = Agreement.objects.get()
        self.assertEqual(agreement.bond_id, bond.id)
        self.assertEqual(agreement.student_name, "Aku Banda")
        self.assertEqual(agreement.programme, "BSc Computer Science")
        self.assertEqual(agreement.tuition_amount, Decimal("450000.00"))
        self.assertEqual(agreement.total_amount, bond.amount)
        self.assertEqual(bond.amount, Decimal("500000.00"))
        self.assertEqual(bond.registration_number, "REG-001")
        self.assertEqual(bond.documents.count(), len(COMPULSORY_DOCUMENT_TYPES))
        self.assertIsNotNone(bond.academic_year_id)

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

        # Generating again does not create a second agreement.
        self.client.force_authenticate(self.student)
        response = self.client.post(reverse("agreement-generate"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Agreement.objects.count(), 1)

        # Bond history keeps the year, registration, user and amount.
        self.client.force_authenticate(self.admin)
        history = self.client.get(
            reverse("bond-history"),
            {"academic_year": bond.academic_year.label},
        )
        self.assertEqual(history.status_code, 200)
        row = history.data[0]
        self.assertEqual(row["registration_number"], "REG-001")
        self.assertEqual(row["user"], "student1")
        self.assertEqual(Decimal(row["amount"]), Decimal("500000.00"))
        self.assertEqual(row["full_name"], "Aku Banda")

        # The bond can be approved only after the agreement exists.
        response = self.approve_bond(bond.id)
        self.assertEqual(response.status_code, 200, response.data)
        bond.refresh_from_db()
        self.assertEqual(bond.status, "approved")

        agreement_number = str(agreement.agreement_number)

        sign_url = reverse(
            "agreement-sign", kwargs={"agreement_number": agreement_number}
        )
        countersign_url = reverse(
            "agreement-countersign",
            kwargs={"agreement_number": agreement_number},
        )

        def upload_signed(url, user):
            self.client.force_authenticate(user)
            return self.client.post(
                url, {"signed_document": signed_pdf()}, format="multipart"
            )

        # Countersigning before the student signs is refused.
        self.assertEqual(
            upload_signed(countersign_url, self.officer).status_code, 400
        )

        # Another student cannot sign it.
        self.assertEqual(
            upload_signed(sign_url, self.other_student).status_code, 403
        )

        # 6. The owner signs the downloaded template.
        self.assertEqual(upload_signed(sign_url, self.student).status_code, 200)

        # Only the Loan Board Officer may countersign.
        for user in (self.student, self.admin):
            self.assertEqual(upload_signed(countersign_url, user).status_code, 403)

        # 7. The officer countersigns.
        self.assertEqual(
            upload_signed(countersign_url, self.officer).status_code, 200
        )
        self.assertEqual(
            Agreement.objects.get().status, Agreement.Status.COUNTERSIGNED
        )

        # The PDF can be downloaded.
        self.client.force_authenticate(self.student)
        response = self.client.get(
            reverse(
                "agreement-download",
                kwargs={"agreement_number": agreement_number},
            )
        )
        self.assertEqual(response.status_code, 200)

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

    def test_a_new_academic_year_does_not_overwrite_the_bond(self):
        self.upload_and_verify_all(self.student)
        first = Bond.objects.get(student=self.student)
        first_amount = first.amount
        first_year = first.academic_year.label

        next_year = get_or_create_academic_year("2027")
        second_application = LoanApplication.objects.create(
            owner=self.student,
            academic_year=next_year,
            tuition_amount=Decimal("10.00"),
            upkeep_amount=Decimal("5.00"),
        )
        for doc_type in COMPULSORY_DOCUMENT_TYPES:
            doc_id = self.upload(
                doc_type,
                self.student,
                loan_application=second_application.id,
            )
            response = self.review(doc_id)
            self.assertEqual(response.status_code, 200, response.data)

        self.assertEqual(Bond.objects.filter(student=self.student).count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.amount, first_amount)
        self.assertEqual(first.academic_year.label, first_year)

        second = Bond.objects.get(student=self.student, academic_year=next_year)
        self.assertEqual(second.amount, Decimal("15.00"))
        self.assertEqual(second.status, "pending")
        self.assertEqual(second.agreement.total_amount, Decimal("15.00"))
        self.assertEqual(second.agreement.academic_year_label, "2027")

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