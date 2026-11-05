from django.test import TestCase


from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Bond, BondStatusHistory


User = get_user_model()


class BondHistoryTests(APITestCase):

    def setUp(self):
        self.student = User.objects.create_user(
            username="test_student",
            password="Student123!"
        )

        self.staff = User.objects.create_user(
            username="test_staff",
            password="Staff123!",
            is_staff=True
        )

        self.bond = Bond.objects.create(
            student=self.student,
            status="pending"
        )

        self.url = reverse(
            "bond-status-update",
            kwargs={"pk": self.bond.pk}
        )

        self.client.force_authenticate(
            user=self.staff
        )

    def test_status_change_creates_history(self):
        response = self.client.patch(
            self.url,
            {"status": "approved"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.bond.refresh_from_db()
        self.assertEqual(
            self.bond.status,
            "approved"
        )

        history = BondStatusHistory.objects.get(
            bond=self.bond
        )

        self.assertEqual(
            history.previous_status,
            "pending"
        )

        self.assertEqual(
            history.new_status,
            "approved"
        )

        self.assertEqual(
            history.changed_by,
            self.staff
        )

        self.assertIsNotNone(history.changed_at)

    def test_same_status_does_not_create_history(self):
        response = self.client.patch(
            self.url,
            {"status": "pending"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            BondStatusHistory.objects.filter(
                bond=self.bond
            ).count(),
            0
        )

