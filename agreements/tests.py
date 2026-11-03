from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Agreement


User = get_user_model()


class AgreementAPITests(APITestCase):

    def setUp(self):
        # Create a student account
        self.student = User.objects.create_user(
            username="student1",
            password="TestPassword123"
        )

        # Create another student account
        self.other_student = User.objects.create_user(
            username="student2",
            password="TestPassword123"
        )

        # Create a university administrator
        self.admin = User.objects.create_user(
            username="admin1",
            password="TestPassword123",
            is_staff=True
        )

        self.generate_url = reverse("agreement-generate")
        self.list_url = reverse("agreement-list")

        self.client.force_authenticate(user=self.student)

    # -----------------------------------------
    # AGREEMENT GENERATION TESTS
    # -----------------------------------------

    def test_student_can_generate_own_agreement(self):

        response = self.client.post(
            self.generate_url,
            {
                "student_id": self.student.username,
                "loan_reference": "LOAN-001"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            Agreement.objects.count(),
            1
        )

        agreement = Agreement.objects.first()

        self.assertEqual(
            agreement.student_id,
            self.student.username
        )

        self.assertEqual(
            agreement.loan_reference,
            "LOAN-001"
        )

        self.assertEqual(
            agreement.status,
            Agreement.Status.GENERATED
        )

    def test_student_cannot_generate_agreement_for_another_student(self):

        response = self.client.post(
            self.generate_url,
            {
                "student_id": self.other_student.username,
                "loan_reference": "LOAN-002"
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

        self.assertEqual(
            Agreement.objects.count(),
            0
        )

    def test_generation_requires_student_id_and_loan_reference(self):

        response = self.client.post(
            self.generate_url,
            {
                "student_id": self.student.username
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_generation_rejects_empty_values(self):

        response = self.client.post(
            self.generate_url,
            {
                "student_id": "",
                "loan_reference": ""
            },
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # AGREEMENT RETRIEVAL TESTS
    # -----------------------------------------

    def test_student_can_view_own_agreements(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-003",
            agreement_content="Test agreement"
        )

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data),
            1
        )

        self.assertEqual(
            str(response.data[0]["agreement_number"]),
            str(agreement.agreement_number)
        )

    def test_student_cannot_view_another_students_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.other_student.username,
            loan_reference="LOAN-004",
            agreement_content="Another student's agreement"
        )

        detail_url = reverse(
            "agreement-detail",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.get(detail_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )

    def test_admin_can_view_all_agreements(self):

        Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-005",
            agreement_content="Student one agreement"
        )

        Agreement.objects.create(
            student_id=self.other_student.username,
            loan_reference="LOAN-006",
            agreement_content="Student two agreement"
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data),
            2
        )

    # -----------------------------------------
    # STUDENT SIGNING TESTS
    # -----------------------------------------

    def test_student_can_sign_own_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-007",
            agreement_content="Test agreement"
        )

        sign_url = reverse(
            "agreement-sign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(sign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        agreement.refresh_from_db()

        self.assertEqual(
            agreement.status,
            Agreement.Status.SIGNED
        )

        self.assertIsNotNone(
            agreement.student_signed_at
        )

    def test_student_cannot_sign_another_students_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.other_student.username,
            loan_reference="LOAN-008",
            agreement_content="Another student's agreement"
        )

        sign_url = reverse(
            "agreement-sign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(sign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )

    def test_student_cannot_sign_already_signed_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-009",
            agreement_content="Test agreement",
            status=Agreement.Status.SIGNED,
            student_signed_at=timezone.now()
        )

        sign_url = reverse(
            "agreement-sign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(sign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    # -----------------------------------------
    # ADMINISTRATOR COUNTERSIGNING TESTS
    # -----------------------------------------

    def test_admin_can_countersign_student_signed_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-010",
            agreement_content="Test agreement",
            status=Agreement.Status.SIGNED,
            student_signed_at=timezone.now()
        )

        self.client.force_authenticate(user=self.admin)

        countersign_url = reverse(
            "agreement-countersign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(countersign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        agreement.refresh_from_db()

        self.assertEqual(
            agreement.status,
            Agreement.Status.COUNTERSIGNED
        )

        self.assertIsNotNone(
            agreement.board_countersigned_at
        )

    def test_admin_cannot_countersign_unsigned_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-011",
            agreement_content="Test agreement"
        )

        self.client.force_authenticate(user=self.admin)

        countersign_url = reverse(
            "agreement-countersign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(countersign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

    def test_student_cannot_countersign_agreement(self):

        agreement = Agreement.objects.create(
            student_id=self.student.username,
            loan_reference="LOAN-012",
            agreement_content="Test agreement",
            status=Agreement.Status.SIGNED,
            student_signed_at=timezone.now()
        )

        countersign_url = reverse(
            "agreement-countersign",
            kwargs={
                "agreement_number": agreement.agreement_number
            }
        )

        response = self.client.post(countersign_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN
        )