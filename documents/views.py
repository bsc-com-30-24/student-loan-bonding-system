
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse

from .models import Document


class RoleBasedLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        if self.request.user.is_staff:
            return "/admin/"
        return reverse("submit_document")


@login_required
def submit_document(request):
    if request.user.is_staff:
        raise PermissionDenied

    if request.method == "POST":
        document_type = request.POST.get("document_type")
        uploaded_file = request.FILES.get("file")

        if not document_type or not uploaded_file:
            messages.error(
                request,
                "Please select a document type and upload a file."
            )
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
