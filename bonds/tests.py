from django.test import TestCase


from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Bond, BondStatusHistory

from django.contrib import admin
from django.test import RequestFactory

from .admin import BondAdmin


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


    def test_student_can_view_own_bond_history(self):
        # First, the staff member approves the bond.
        self.client.patch(
            self.url,
            {"status": "approved"},
            format="json"
        )

        # Now authenticate as the student.
        self.client.force_authenticate(
            user=self.student
        )

        # Request the history of the student's bond.
        history_url = reverse(
            "bond-status-history",
            kwargs={"pk": self.bond.pk}
        )

        response = self.client.get(history_url)

        # The student should be allowed to view it.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # There should be one history record.
        self.assertEqual(len(response.data), 1)

        # Confirm the status transition is correct.
        self.assertEqual(
            response.data[0]["previous_status"],
            "pending"
        )

        self.assertEqual(
            response.data[0]["new_status"],
            "approved"
        )

    def test_student_cannot_view_another_students_bond_history(self):
        # Create a second student.
        another_student = User.objects.create_user(
            username="another_student",
            password="Student123!"
        )

        # Create a bond belonging to the second student.
        another_bond = Bond.objects.create(
            student=another_student,
            status="pending"
        )

        # Create a history record for the second student's bond.
        BondStatusHistory.objects.create(
            bond=another_bond,
            previous_status="pending",
            new_status="approved",
            changed_by=self.staff,
            reason="Approved by staff"
        )

        # Authenticate as the first student.
        self.client.force_authenticate(user=self.student)

        # Attempt to access the second student's bond history.
        history_url = reverse(
            "bond-status-history",
            kwargs={"pk": another_bond.pk}
        )

        response = self.client.get(history_url)

        # Access must be denied.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )


    def test_staff_can_view_bond_history(self):
        # Staff member updates the bond status.
        response = self.client.patch(
            self.url,
            {"status": "approved"},
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # Get the history endpoint URL.
        history_url = reverse(
            "bond-status-history",
            kwargs={"pk": self.bond.pk}
        )

        # Staff member requests the bond history.
        response = self.client.get(history_url)

        # Staff should be allowed to view the history.
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # Confirm that one history record exists.
        self.assertEqual(len(response.data), 1)

        # Confirm the correct staff member is recorded.
        self.assertEqual(
            response.data[0]["changed_by"],
            self.staff.id
        )

        self.assertEqual(
            response.data[0]["changed_by_username"],
            self.staff.username
        )


    def test_unauthenticated_user_cannot_view_bond_history(self):
        # Get the history URL.
        history_url = reverse(
            "bond-status-history",
            kwargs={"pk": self.bond.pk}
        )

        # Log out the authenticated staff user.
        self.client.force_authenticate(user=None)

        # Try accessing history without logging in.
        response = self.client.get(history_url)

        # The request must be rejected.
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )


    def test_bond_history_shows_latest_change_first(self):
        # First status change: pending to approved.
        first_response = self.client.patch(
            self.url,
            {"status": "approved"},
            format="json"
        )

        self.assertEqual(
            first_response.status_code,
            status.HTTP_200_OK
        )

        # Second status change: approved to completed.
        second_response = self.client.patch(
            self.url,
            {"status": "completed"},
            format="json"
        )

        self.assertEqual(
            second_response.status_code,
            status.HTTP_200_OK
        )

        # Request the bond history.
        history_url = reverse(
            "bond-status-history",
            kwargs={"pk": self.bond.pk}
        )

        response = self.client.get(history_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        # Both changes should be recorded.
        self.assertEqual(len(response.data), 2)

        # The latest change should appear first.
        self.assertEqual(
            response.data[0]["previous_status"],
            "approved"
        )

        self.assertEqual(
            response.data[0]["new_status"],
            "completed"
        )

        # The earlier change should appear second.
        self.assertEqual(
            response.data[1]["previous_status"],
            "pending"
        )

        self.assertEqual(
            response.data[1]["new_status"],
            "approved"
        )


    def test_admin_status_change_creates_history(self):
        # Create a simulated Django Admin request.
        request = RequestFactory().post(
            "/admin/bonds/bond/"
        )
        request.user = self.staff

        # Administrator changes the status.
        self.bond.status = "approved"

        # Call the Django Admin save method.
        bond_admin = BondAdmin(Bond, admin.site)

        bond_admin.save_model(
            request,
            self.bond,
            form=None,
            change=True,
        )

        # Refresh the bond from the database.
        self.bond.refresh_from_db()

        self.assertEqual(
            self.bond.status,
            "approved"
        )

        # Confirm the history record was created.
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

        self.assertIsNotNone(
            history.changed_at
        )


    def test_admin_same_status_does_not_create_history(self):
        # Simulate a Django Admin request.
        request = RequestFactory().post(
            "/admin/bonds/bond/"
        )
        request.user = self.staff

        # Change the rejection reason, but not the status.
        self.bond.rejection_reason = "Administrative note"

        # Save the bond through Django Admin.
        bond_admin = BondAdmin(Bond, admin.site)

        bond_admin.save_model(
            request,
            self.bond,
            form=None,
            change=True,
        )

        # Confirm the bond still has its original status.
        self.bond.refresh_from_db()

        self.assertEqual(
            self.bond.status,
            "pending"
        )

        # No history record should have been created.
        self.assertEqual(
            BondStatusHistory.objects.filter(
                bond=self.bond
            ).count(),
            0
        )


    def test_direct_model_status_change_creates_history(self):
        # Change the status directly through Django.
        self.bond.status = "approved"
        self.bond.save()

        # Confirm the bond was updated.
        self.bond.refresh_from_db()

        self.assertEqual(
            self.bond.status,
            "approved"
        )

        # A history record should also be created.
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

        self.assertIsNotNone(history.changed_at)

        # A direct model save has no authenticated
        # request, so the actor is unknown.
        self.assertIsNone(history.changed_by)
