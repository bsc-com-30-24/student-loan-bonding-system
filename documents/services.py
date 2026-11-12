from decimal import Decimal

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from agreements.models import Agreement
from agreements.pdf_utils import generate_agreement_pdf
from authentication.models import LoanApplication
from bonds.academic import get_current_academic_year
from bonds.models import Bond

from .models import Document, Notification

# Document types a student must have verified before a bond is generated.
# All other types (affidavit, guarantor_form, guarantor_id, other_letter)
# are optional. Edit this tuple to change the rule.
COMPULSORY_DOCUMENT_TYPES = (
    "student_id",
    "national_id",
)

MONEY = Decimal("0.01")


def student_record(user):
    """Personal details kept on the student, copied onto the agreement."""
    return getattr(user, "student_detail", None)


def student_display_name(user):
    detail = student_record(user)
    if detail is not None and detail.full_name.strip():
        return detail.full_name.strip()
    full_name = user.get_full_name().strip()
    return full_name or user.get_username()


def registration_number_for(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "student_registration_number", None) or ""


def programme_for(user):
    detail = student_record(user)
    return (detail.programme if detail is not None else "") or ""


def resolve_loan_application(student, application_id=None):
    """The application whose amounts and year the documents belong to."""
    if application_id:
        return LoanApplication.objects.filter(
            pk=application_id, owner=student
        ).select_related("academic_year").first()

    current_year = get_current_academic_year()
    return (
        LoanApplication.objects.filter(owner=student, academic_year=current_year)
        .select_related("academic_year")
        .order_by("-created_at")
        .first()
    )


def has_all_compulsory_documents_verified(student, loan_application):
    verified_types = set(
        Document.objects.filter(
            student=student,
            loan_application=loan_application,
            status="verified",
            document_type__in=COMPULSORY_DOCUMENT_TYPES,
        ).values_list("document_type", flat=True)
    )
    return verified_types.issuperset(COMPULSORY_DOCUMENT_TYPES)


def build_agreement_content(bond, agreement_amounts):
    year = bond.academic_year.label if bond.academic_year_id else ""
    year_of_study = agreement_amounts.get("year_of_study") or "-"
    phone = agreement_amounts.get("phone_number") or "-"
    return (
        "STUDENT LOAN BONDING AGREEMENT\n\n"
        f"Academic year: {year}\n"
        f"Student: {agreement_amounts['student_name']}\n"
        f"Registration number: {bond.registration_number}\n"
        f"Programme: {agreement_amounts['programme'] or '-'}\n"
        f"Year of study: {year_of_study}\n"
        f"Phone: {phone}\n"
        f"Loan reference: {agreement_amounts['loan_reference']}\n"
        f"Bond reference: {bond.bond_reference}\n\n"
        f"Tuition fees: {bond.tuition_amount}\n"
        f"Upkeep: {bond.upkeep_amount}\n"
        f"Total amount: {bond.amount}\n\n"
        "This agreement records the bonding arrangement for the academic "
        "year above. The amounts and the student details are taken from "
        "the submitted application and verified documents. A later academic "
        "year receives its own bond and does not change this record.\n\n"
        "The bond stays pending until a university administrator approves "
        "the generated agreement."
    )


def _create_agreement(bond, application, student):
    loan_reference = application.loan_reference or str(bond.bond_reference)
    detail = student_record(student)
    details = {
        "student_name": student_display_name(student),
        "programme": programme_for(student),
        "year_of_study": detail.year_of_study if detail is not None else None,
        "phone_number": (detail.phone_number if detail is not None else "") or "",
        "loan_reference": loan_reference,
    }
    agreement = Agreement(
        bond=bond,
        student_id=bond.registration_number or str(student.pk),
        loan_reference=loan_reference,
        student_name=details["student_name"],
        programme=details["programme"],
        year_of_study=details["year_of_study"],
        phone_number=details["phone_number"],
        academic_year_label=(
            bond.academic_year.label if bond.academic_year_id else ""
        ),
        tuition_amount=bond.tuition_amount,
        upkeep_amount=bond.upkeep_amount,
        total_amount=bond.amount,
        status=Agreement.Status.GENERATED,
    )
    agreement.agreement_content = build_agreement_content(bond, details)
    agreement.save()

    pdf_data = generate_agreement_pdf(agreement)
    agreement.generated_pdf.save(
        f"agreement_{agreement.agreement_number}.pdf",
        ContentFile(pdf_data),
        save=True,
    )
    return agreement


def generate_bond_if_eligible(student, triggering_document):
    """
    When every compulsory document for one application is verified, create
    one pending bond for that academic year and generate its agreement.

    Returns (bond, created). created is False when this year already has a
    bond: the existing amount and agreement are left as they are.

    Call this inside the same transaction as the document review.
    """
    application = triggering_document.loan_application
    if application is None:
        return None, False

    if triggering_document.document_type not in COMPULSORY_DOCUMENT_TYPES:
        # Optional documents can still be attached after the bond exists.
        existing = Bond.objects.filter(
            student=student,
            academic_year=application.academic_year,
        ).first()
        if existing is not None and triggering_document.status == "verified":
            existing.documents.add(triggering_document)
        return existing, False

    if not has_all_compulsory_documents_verified(student, application):
        return None, False

    academic_year = application.academic_year or get_current_academic_year()
    existing = (
        Bond.objects.filter(student=student, academic_year=academic_year)
        .select_related("academic_year")
        .first()
    )
    if existing is not None:
        # Do not overwrite the amount, application or agreement already stored.
        if triggering_document.status == "verified":
            existing.documents.add(triggering_document)
        return existing, False

    tuition = application.tuition_amount or Decimal("0.00")
    upkeep = application.upkeep_amount or Decimal("0.00")
    total = (tuition + upkeep).quantize(MONEY)

    try:
        with transaction.atomic():
            bond = Bond.objects.create(
                student=student,
                academic_year=academic_year,
                loan_application=application,
                registration_number=registration_number_for(student),
                tuition_amount=tuition,
                upkeep_amount=upkeep,
                amount=total,
                status="pending",
            )
            verified_documents = Document.objects.filter(
                student=student,
                loan_application=application,
                status="verified",
            )
            bond.documents.set(verified_documents)
            _create_agreement(bond, application, student)
    except IntegrityError:
        return (
            Bond.objects.filter(
                student=student, academic_year=academic_year
            ).first(),
            False,
        )

    Notification.objects.create(
        student=student,
        document=triggering_document,
        message=(
            f"Your documents for {academic_year.label} have been verified. "
            f"Bond {bond.bond_reference} and its agreement "
            f"(amount {bond.amount}) were generated and are pending approval."
        ),
    )
    return bond, True
