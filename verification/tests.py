from django.test import TestCase


from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient


class BondVerificationTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = "/api/verification/bonds/12/"
        self.user_model = get_user_model()

    def create_user(self, username, role=None):
        user = self.user_model.objects.create_user(
            username=username,
            password="TestPassword123!"
        )

        if role:
            group, created = Group.objects.get_or_create(
                name=role
            )
            user.groups.add(group)

        return user

    def test_unauthenticated_user(self):
        response = self.client.get(
            self.url,
            HTTP_HOST="localhost"
        )

        self.assertIn(response.status_code, [401, 403])

    def test_student_cannot_verify(self):
        student = self.create_user("student")

        self.client.force_authenticate(user=student)

        response = self.client.get(
            self.url,
            HTTP_HOST="localhost"
        )

        self.assertEqual(response.status_code, 403)

    def test_university_admin_access(self):
        admin = self.create_user(
            "university_admin_test",
            "university_admin"
        )

        self.client.force_authenticate(user=admin)

        response = self.client.get(
            self.url,
            HTTP_HOST="localhost"
        )

        self.assertEqual(response.status_code, 503)

    def test_employer_access(self):
        employer = self.create_user(
            "employer_test",
            "employer"
        )

        self.client.force_authenticate(user=employer)

        response = self.client.get(
            self.url,
            HTTP_HOST="localhost"
        )

        self.assertEqual(response.status_code, 503)

