
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Document


@login_required
def submit_document(request):
    if request.method == "POST":
        document_type = request.POST.get("document_type")
        uploaded_file = request.FILES.get("file")

        if not document_type or not uploaded_file:
            messages.error(request, "Please select a document type and upload a file.")
            return redirect("submit_document")

        Document.objects.create(
            student=request.user,
            document_type=document_type,
            file=uploaded_file,
            status="pending"
        )

        messages.success(request, "Document submitted successfully.")
        return redirect("submit_document")

    return render(request, "documents/submit_document.html")
