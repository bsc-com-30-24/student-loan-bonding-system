from django.db import models
from django.conf import settings


def get_user_role(user):
	if user.is_superuser:
		return "university_admin"
	try:
		return user.profile.role
	except UserProfile.DoesNotExist:
		return UserProfile.Role.STUDENT


class UserProfile(models.Model):
	class Role(models.TextChoices):
		STUDENT = "student", "Student"
		UNIVERSITY_ADMIN = "university_admin", "University Admin"
		LOAN_BOARD_OFFICER = "loan_board_officer", "Loan Board Officer"
		EMPLOYER = "employer", "Employer"

	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	role = models.CharField(max_length=32, choices=Role.choices, default=Role.STUDENT)

	def __str__(self):
		return f"{self.user.username} ({self.role})"


class LoanApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loan_applications",
    )
    tuition_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    upkeep_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


    def get_total_amount(self):
        return self.tuition_amount + self.upkeep_amount

    def __str__(self):
        return f"Loan application {self.pk} (Total: {self.get_total_amount()})"

class PasswordResetOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
