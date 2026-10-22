from django.test import TestCase


from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient


class ReportingAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()

        self.urls = [
            "/api/reports/active-loans/",
            "/api/reports/signed-bonds/",
            "/api/reports/defaulters/",
        ]

        self.student = self.user_model.objects.create_user(
            username="test_student",
            password="TestPassword123!"
        )

        self.officer = self.user_model.objects.create_user(
            username="test_officer",
            password="TestPassword123!"
        )

        group, created = Group.objects.get_or_create(
            name="loan_board_officer"
        )

        self.officer.groups.add(group)

    def test_unauthenticated_access(self):
        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(
                    url,
                    HTTP_HOST="localhost"
                )

                self.assertIn(
                    response.status_code,
                    [401, 403]
                )

    def test_student_access_denied(self):
        self.client.force_authenticate(user=self.student)

        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(
                    url,
                    HTTP_HOST="localhost"
                )

                self.assertEqual(response.status_code, 403)

    def test_loan_board_officer_access(self):
        self.client.force_authenticate(user=self.officer)

        for url in self.urls:
            with self.subTest(url=url):
                response = self.client.get(
                    url,
                    HTTP_HOST="localhost"
                )

                self.assertEqual(response.status_code, 503)

                self.assertEqual(
                    response.data["message"],
                    "Report data integration is pending."
                )

