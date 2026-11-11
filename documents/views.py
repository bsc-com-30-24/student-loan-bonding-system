from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import render, redirect
from django.urls import reverse

from authentication.models import UserProfile, get_user_role

from .models import Document
from .validators import validate_uploaded_document


class RoleBasedLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        if self.request.user.is_staff:
            return "/admin/"

        return reverse("submit_document")


@login_required
def submit_document(request):
    if (
        request.user.is_staff
        or get_user_role(request.user) != UserProfile.Role.STUDENT
    ):
        raise PermissionDenied(
            "Only students can submit documents."
        )

    if request.method == "POST":
        document_type = request.POST.get("document_type")
        uploaded_file = request.FILES.get("file")

        valid_types = {key for key, _ in Document.DOCUMENT_TYPES}

        if document_type not in valid_types or not uploaded_file:
            messages.error(
                request,
                "Please select a document type and upload a file."
            )
            return redirect("submit_document")

        try:
            validate_uploaded_document(uploaded_file)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect("submit_document")

        Document.objects.create(
            student=request.user,
            document_type=document_type,
            file=uploaded_file,
            status="pending",
        )

        messages.success(
            request,
            "Document submitted successfully."
        )

        return redirect("submit_document")

    return render(
        request,
        "documents/submit_document.html"
    )