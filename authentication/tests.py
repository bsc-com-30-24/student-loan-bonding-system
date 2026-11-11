import re
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import LoanApplication, PasswordResetOTP, UserProfile

User = get_user_model()

REGISTER_URL = "/api/register/"
TOKEN_URL = "/api/token/"
REFRESH_URL = "/api/token/refresh/"
RESET_REQUEST_URL = "/api/password-reset/"
RESET_CONFIRM_URL = "/api/password-reset/confirm/"
LOANS_URL = "/api/loans/"

STRONG = "Strong-test-password-2026!"

GOOD = {
    "username": "aku",
    "email": "aku@example.com",
    "student_registration_number": "BSCS/2025/001",
    "password": "AKU@2027Pass",
    "password_confirmation": "AKU@2027Pass",
}


class RegistrationTests(APITestCase):
    def setUp(self):
        cache.clear()  # reset throttle counters

    def test_success_hides_secrets_and_creates_student_profile(self):
        r = self.client.post(REGISTER_URL, GOOD, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(set(r.data), {"id", "username", "email"})
        user = User.objects.get(username="aku")
        self.assertEqual(user.profile.role, UserProfile.Role.STUDENT)
        self.assertEqual(user.profile.student_registration_number, "BSCS/2025/001")

    def test_registration_number_is_normalised_to_uppercase(self):
        data = {**GOOD, "student_registration_number": "  bscs/2025/009 "}
        self.assertEqual(
            self.client.post(REGISTER_URL, data, format="json").status_code, 201
        )
        self.assertEqual(
            User.objects.get(username="aku").profile.student_registration_number,
            "BSCS/2025/009",
        )

    def test_role_in_payload_is_ignored_and_jwt_returns_role(self):
        payload = {**GOOD, "role": UserProfile.Role.LOAN_BOARD_OFFICER}
        r = self.client.post(REGISTER_URL, payload, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(User.objects.get(username="aku").profile.role, "student")

        token = self.client.post(
            TOKEN_URL, {"username": "aku", "password": GOOD["password"]}, format="json"
        )
        self.assertEqual(token.status_code, 200)
        self.assertEqual(token.data["role"], UserProfile.Role.STUDENT)
        self.assertIn("access", token.data)
        self.assertIn("refresh", token.data)

        refresh = self.client.post(
            REFRESH_URL, {"refresh": token.data["refresh"]}, format="json"
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertIn("access", refresh.data)

    def test_invalid_bearer_token_is_ignored(self):
        r = self.client.post(
            REGISTER_URL, GOOD, format="json", HTTP_AUTHORIZATION="Bearer garbage"
        )
        self.assertEqual(r.status_code, 201)

    def test_duplicates_rejected(self):
        self.client.post(REGISTER_URL, GOOD, format="json")
        base = {
            **GOOD,
            "username": "other",
            "email": "o@example.com",
            "student_registration_number": "X/1",
        }
        for change in (
            {"username": "aku"},
            {"email": "AKU@example.com"},
            {"student_registration_number": "bscs/2025/001"},
        ):
            r = self.client.post(REGISTER_URL, {**base, **change}, format="json")
            self.assertEqual(r.status_code, 400, change)

    def test_bad_input_creates_nothing(self):
        weak = {"password": "12345678", "password_confirmation": "12345678"}
        for change in ({"password_confirmation": "nope"}, weak):
            r = self.client.post(REGISTER_URL, {**GOOD, **change}, format="json")
            self.assertEqual(r.status_code, 400)
        for missing in ("email", "student_registration_number", "username"):
            data = {k: v for k, v in GOOD.items() if k != missing}
            self.assertEqual(
                self.client.post(REGISTER_URL, data, format="json").status_code, 400
            )
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UserProfile.objects.count(), 0)


class PasswordResetTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("bob", "bob@example.com", "OldPass#2027x")

    def _request_otp(self, email="BOB@example.com"):
        self.client.post(RESET_REQUEST_URL, {"email": email}, format="json")
        return PasswordResetOTP.objects.get(email="bob@example.com")

    def _confirm(self, otp, pw="NewPass#2027y"):
        return self.client.post(
            RESET_CONFIRM_URL,
            {
                "email": "bob@example.com",
                "otp": otp,
                "new_password": pw,
                "password_confirmation": pw,
            },
            format="json",
        )

    def test_unknown_email_gives_same_response_and_sends_nothing(self):
        r = self.client.post(
            RESET_REQUEST_URL, {"email": "nobody@example.com"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_full_flow_via_email_and_single_use(self):
        r = self.client.post(RESET_REQUEST_URL, {"email": "bob@example.com"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["bob@example.com"])
        otp = re.search(r"OTP is: (\d{6})", mail.outbox[0].body).group(1)

        self.assertEqual(self._confirm(otp).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass#2027y"))
        self.assertEqual(self._confirm(otp, "Another#2027z").status_code, 400)

        login = self.client.post(
            TOKEN_URL, {"username": "bob", "password": "NewPass#2027y"}, format="json"
        )
        self.assertEqual(login.status_code, 200)

    def test_wrong_otp_locks_after_five_attempts(self):
        record = self._request_otp()
        wrong = "000000" if record.otp != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self._confirm(wrong).status_code, 400)
        self.assertEqual(self._confirm(record.otp).status_code, 400)  # now locked

    def test_expired_otp(self):
        record = self._request_otp()
        PasswordResetOTP.objects.filter(pk=record.pk).update(
            created_at=timezone.now() - timedelta(minutes=11)
        )
        self.assertEqual(self._confirm(record.otp).status_code, 400)

    def test_weak_new_password_rejected(self):
        record = self._request_otp()
        self.assertEqual(self._confirm(record.otp, "12345678").status_code, 400)

    def test_non_ascii_otp_is_a_400_not_a_500(self):
        self._request_otp()
        self.assertEqual(self._confirm("é12345").status_code, 400)


class LoanAccessTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.student = self.create_user("student", UserProfile.Role.STUDENT)
        self.other_student = self.create_user("other_student", UserProfile.Role.STUDENT)
        self.university_admin = self.create_user(
            "university_admin", UserProfile.Role.UNIVERSITY_ADMIN
        )
        self.loan_officer = self.create_user(
            "loan_officer", UserProfile.Role.LOAN_BOARD_OFFICER
        )
        self.employer = self.create_user("employer", UserProfile.Role.EMPLOYER)
        self.application = LoanApplication.objects.create(
            owner=self.student,
            tuition_amount=Decimal("800.00"),
            upkeep_amount=Decimal("200.00"),
        )
        self.other_application = LoanApplication.objects.create(
            owner=self.other_student,
            tuition_amount=Decimal("1500.00"),
            upkeep_amount=Decimal("500.00"),
        )

    def create_user(self, username, role):
        user = User.objects.create_user(
            username=username, email=f"{username}@example.com", password=STRONG
        )
        UserProfile.objects.create(user=user, role=role)
        return user

    def test_private_endpoints_require_authentication(self):
        self.assertEqual(self.client.get(LOANS_URL).status_code, 401)

    def test_students_are_limited_to_their_own_applications(self):
        self.client.force_authenticate(self.student)
        r = self.client.get(LOANS_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i["id"] for i in r.data], [self.application.id])
        self.assertEqual(
            self.client.get(f"{LOANS_URL}{self.other_application.id}/").status_code, 404
        )

    def test_student_creation_assigns_owner_pending_status_and_reference(self):
        self.client.force_authenticate(self.student)
        r = self.client.post(
            LOANS_URL,
            {
                "owner": self.other_student.id,
                "tuition_amount": "1000.00",
                "upkeep_amount": "500.00",
                "status": LoanApplication.Status.APPROVED,
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        created = LoanApplication.objects.get(id=r.data["id"])
        self.assertEqual(created.owner, self.student)
        self.assertEqual(created.status, LoanApplication.Status.PENDING)
        self.assertTrue(r.data["loan_reference"].startswith("SLBS-"))
        self.assertEqual(r.data["amount"], Decimal("1500.00"))

    def test_invalid_amounts_rejected(self):
        self.client.force_authenticate(self.student)
        for tuition, upkeep in (("-500.00", "1000.00"), ("0.00", "0.00")):
            r = self.client.post(
                LOANS_URL,
                {"tuition_amount": tuition, "upkeep_amount": upkeep},
                format="json",
            )
            self.assertEqual(r.status_code, 400, (tuition, upkeep))

    def test_admin_and_officer_can_read_all_but_employer_cannot(self):
        for user in (self.university_admin, self.loan_officer):
            self.client.force_authenticate(user)
            r = self.client.get(LOANS_URL)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(r.data), 2)
        self.client.force_authenticate(self.employer)
        self.assertEqual(self.client.get(LOANS_URL).status_code, 403)

    def test_only_loan_officer_can_change_application_status(self):
        url = f"{LOANS_URL}{self.application.id}/"
        approved = {"status": LoanApplication.Status.APPROVED}

        self.client.force_authenticate(self.university_admin)
        self.assertEqual(self.client.patch(url, approved, format="json").status_code, 403)

        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.patch(url, approved, format="json").status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, LoanApplication.Status.PENDING)

        # Status-only PATCH must work (regression: validate() used to see 0 + 0).
        self.client.force_authenticate(self.loan_officer)
        self.assertEqual(self.client.patch(url, approved, format="json").status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, LoanApplication.Status.APPROVED)

    def test_student_cannot_edit_or_delete_non_pending_application(self):
        LoanApplication.objects.filter(pk=self.application.pk).update(
            status=LoanApplication.Status.APPROVED
        )
        url = f"{LOANS_URL}{self.application.id}/"
        self.client.force_authenticate(self.student)
        self.assertEqual(
            self.client.patch(url, {"tuition_amount": "900.00"}, format="json").status_code,
            403,
        )
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_student_can_delete_pending_application(self):
        self.client.force_authenticate(self.student)
        r = self.client.delete(f"{LOANS_URL}{self.application.id}/")
        self.assertEqual(r.status_code, 204)