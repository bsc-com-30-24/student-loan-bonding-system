from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase

from .models import LoanApplication, UserProfile

User = get_user_model()


class AuthenticationAndAccessControlTests(APITestCase):
	def setUp(self):
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
			amount="1000.00",
			purpose="Tuition",
		)
		self.other_application = LoanApplication.objects.create(
			owner=self.other_student,
			amount="2000.00",
			purpose="Books",
		)

	def create_user(self, username, role):
		user = User.objects.create_user(
			username=username,
			email=f"{username}@example.com",
			password="Strong-test-password-2026!",
		)
		UserProfile.objects.create(user=user, role=role)
		return user

	def test_password_reset_emails_token_and_changes_password(self):
		request_response = self.client.post(
			"/api/password-reset/",
			{"email": self.student.email},
			format="json",
		)
		self.assertEqual(request_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(mail.outbox), 1)
		self.assertEqual(mail.outbox[0].to, [self.student.email])

		uid, token = [
			line.split(": ", 1)[1]
			for line in mail.outbox[0].body.splitlines()
			if line.startswith(("UID: ", "Token: "))
		]
		new_password = "New-unique-password-2026!"
		reset_response = self.client.post(
			"/api/password-reset/confirm/",
			{
				"uid": uid,
				"token": token,
				"new_password": new_password,
				"password_confirmation": new_password,
			},
			format="json",
		)
		self.assertEqual(reset_response.status_code, status.HTTP_200_OK)
		self.student.refresh_from_db()
		self.assertTrue(self.student.check_password(new_password))

		reused_token_response = self.client.post(
			"/api/password-reset/confirm/",
			{
				"uid": uid,
				"token": token,
				"new_password": new_password,
				"password_confirmation": new_password,
			},
			format="json",
		)
		self.assertEqual(reused_token_response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_password_reset_request_does_not_reveal_unknown_email(self):
		response = self.client.post(
			"/api/password-reset/",
			{"email": "unknown@example.com"},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(mail.outbox), 0)

	def test_private_endpoints_require_authentication(self):
		response = self.client.get("/api/loans/")
		self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

	def test_registration_creates_student_and_jwt_returns_role(self):
		response = self.client.post(
			"/api/register/",
			{
				"username": "new_student",
				"email": "student@example.com",
				"password": "Unique-strong-password-2026!",
				"password_confirmation": "Unique-strong-password-2026!",
				"role": UserProfile.Role.LOAN_BOARD_OFFICER,
			},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		user = User.objects.get(username="new_student")
		self.assertEqual(user.profile.role, UserProfile.Role.STUDENT)

		token_response = self.client.post(
			"/api/token/",
			{
				"username": "new_student",
				"password": "Unique-strong-password-2026!",
			},
			format="json",
		)
		self.assertEqual(token_response.status_code, status.HTTP_200_OK)
		self.assertEqual(token_response.data["role"], UserProfile.Role.STUDENT)
		self.assertIn("access", token_response.data)
		self.assertIn("refresh", token_response.data)

		refresh_response = self.client.post(
			"/api/token/refresh/",
			{"refresh": token_response.data["refresh"]},
			format="json",
		)
		self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
		self.assertIn("access", refresh_response.data)

	def test_students_are_limited_to_their_own_applications(self):
		self.client.force_authenticate(self.student)
		response = self.client.get("/api/loans/")
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual([item["id"] for item in response.data], [self.application.id])

		response = self.client.get(f"/api/loans/{self.other_application.id}/")
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

	def test_student_creation_assigns_owner_and_pending_status(self):
		self.client.force_authenticate(self.student)
		response = self.client.post(
			"/api/loans/",
			{
				"owner": self.other_student.id,
				"amount": "1500.00",
				"purpose": "Housing",
				"status": LoanApplication.Status.APPROVED,
			},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		created_application = LoanApplication.objects.get(id=response.data["id"])
		self.assertEqual(created_application.owner, self.student)
		self.assertEqual(created_application.status, LoanApplication.Status.PENDING)

	def test_admin_and_officer_can_read_all_but_employer_cannot(self):
		for user in (self.university_admin, self.loan_officer):
			self.client.force_authenticate(user)
			response = self.client.get("/api/loans/")
			self.assertEqual(response.status_code, status.HTTP_200_OK)
			self.assertEqual(len(response.data), 2)

		self.client.force_authenticate(self.employer)
		response = self.client.get("/api/loans/")
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_only_loan_officer_can_change_application_status(self):
		self.client.force_authenticate(self.university_admin)
		response = self.client.patch(
			f"/api/loans/{self.application.id}/",
			{"status": LoanApplication.Status.APPROVED},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.force_authenticate(self.student)
		response = self.client.patch(
			f"/api/loans/{self.application.id}/",
			{"status": LoanApplication.Status.APPROVED},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.application.refresh_from_db()
		self.assertEqual(self.application.status, LoanApplication.Status.PENDING)

		self.client.force_authenticate(self.loan_officer)
		response = self.client.patch(
			f"/api/loans/{self.application.id}/",
			{"status": LoanApplication.Status.APPROVED},
			format="json",
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.application.refresh_from_db()
		self.assertEqual(self.application.status, LoanApplication.Status.APPROVED)
