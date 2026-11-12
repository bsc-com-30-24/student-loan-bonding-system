from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def generate_agreement_pdf(agreement):
    """Automatic agreement template: student details and the year's amounts."""
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    def line(text):
        return escape(str(text))

    styles = getSampleStyleSheet()
    story = [
        Paragraph("STUDENT LOAN BONDING AGREEMENT", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            f"Agreement number: {line(agreement.agreement_number)}",
            styles["Normal"],
        ),
        Paragraph(
            f"Academic year: {line(agreement.academic_year_label or '-')}",
            styles["Normal"],
        ),
        Paragraph(
            f"Student: {line(agreement.student_name or agreement.student_id)}",
            styles["Normal"],
        ),
        Paragraph(
            f"Registration number: {line(agreement.student_id)}",
            styles["Normal"],
        ),
        Paragraph(
            f"Programme: {line(agreement.programme or '-')}",
            styles["Normal"],
        ),
        Paragraph(
            f"Year of study: {line(agreement.year_of_study or '-')}",
            styles["Normal"],
        ),
        Paragraph(
            f"Phone: {line(agreement.phone_number or '-')}",
            styles["Normal"],
        ),
        Paragraph(
            f"Loan reference: {line(agreement.loan_reference)}",
            styles["Normal"],
        ),
    ]

    bond = agreement.bond
    if bond is not None:
        story.append(
            Paragraph(
                f"Bond reference: {line(bond.bond_reference)}",
                styles["Normal"],
            )
        )

    story.extend(
        [
            Spacer(1, 16),
            Paragraph("Amounts for this academic year", styles["Heading2"]),
            Paragraph(
                f"Tuition fees: {line(agreement.tuition_amount)}",
                styles["Normal"],
            ),
            Paragraph(
                f"Upkeep: {line(agreement.upkeep_amount)}",
                styles["Normal"],
            ),
            Paragraph(
                f"Total amount: {line(agreement.total_amount)}",
                styles["Normal"],
            ),
            Spacer(1, 16),
            Paragraph(
                line(agreement.agreement_content).replace("\n", "<br/>"),
                styles["Normal"],
            ),
            Spacer(1, 24),
            Paragraph(
                "Student signature: __________________________",
                styles["Normal"],
            ),
            Spacer(1, 16),
            Paragraph(
                "Loan Board Officer signature: __________________________",
                styles["Normal"],
            ),
        ]
    )

    document.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data
