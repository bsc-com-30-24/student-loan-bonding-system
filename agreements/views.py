from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Agreement
from .serializers import (
    AgreementActionResponseSerializer,
    AgreementGenerateRequestSerializer,
    AgreementSerializer,
    ErrorResponseSerializer,
)

AGREEMENT_NUMBER_PARAM = OpenApiParameter(
    name="agreement_number",
    type=OpenApiTypes.UUID,
    location=OpenApiParameter.PATH,
    description="UUID of the agreement (returned when it is generated).",
)


@extend_schema_view(
    get=extend_schema(
        summary="List agreements",
        description=(
            "Staff see all agreements. Students see only their own."
        ),
        tags=["Agreements"],
    )
)
class AgreementListView(generics.ListAPIView):
    serializer_class = AgreementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Agreement.objects.all()

        return Agreement.objects.filter(
            student_id__in=[str(user.pk), user.get_username()]
        )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve an agreement",
        description=(
            "Returns one agreement by its agreement number. Students can "
            "only retrieve their own agreements; any other agreement "
            "returns 404."
        ),
        parameters=[AGREEMENT_NUMBER_PARAM],
        tags=["Agreements"],
    )
)
class AgreementDetailView(generics.RetrieveAPIView):
    serializer_class = AgreementSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'agreement_number'

    def get_queryset(self):
        user = self.request.user

        if user.is_staff:
            return Agreement.objects.all()

        return Agreement.objects.filter(
            student_id__in=[str(user.pk), user.get_username()]
        )


class AgreementGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AgreementGenerateRequestSerializer,
        responses={
            201: AgreementSerializer,
            400: OpenApiResponse(
                ErrorResponseSerializer,
                description="Missing or empty student_id / loan_reference.",
            ),
            403: OpenApiResponse(
                ErrorResponseSerializer,
                description="A student tried to generate an agreement "
                            "for someone else.",
            ),
        },
        summary="Generate a student loan bonding agreement",
        description=(
            "Creates a new agreement. Students may only generate an "
            "agreement for their own student_id (their user id or "
            "username). Staff may generate one for any student."
        ),
        tags=["Agreements"],
    )
    def post(self, request):
        student_id = request.data.get('student_id')
        loan_reference = request.data.get('loan_reference')

        user = request.user

        if student_id is None or loan_reference is None:
            return Response(
                {
                    'error': 'student_id and loan_reference are required.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not student_id or not loan_reference:
            return Response(
                {
                    'error': 'Student ID and loan reference cannot be empty.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.is_staff and str(student_id) not in [
            str(user.pk),
            user.get_username()
        ]:
            return Response(
                {
                    'error': 'You can only generate your own agreement.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        agreement_content = (
            'STUDENT LOAN BONDING AGREEMENT\n'
            f'Student ID: {student_id}\n'
            f'Loan Reference: {loan_reference}\n'
            'Approved agreement terms must be inserted here.'
        )

        agreement = Agreement.objects.create(
            student_id=str(student_id),
            loan_reference=str(loan_reference),
            agreement_content=agreement_content
        )

        serializer = AgreementSerializer(agreement)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )


class AgreementSignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        parameters=[AGREEMENT_NUMBER_PARAM],
        responses={
            200: AgreementActionResponseSerializer,
            400: OpenApiResponse(
                ErrorResponseSerializer,
                description="Agreement is not in a signable status.",
            ),
            403: OpenApiResponse(
                ErrorResponseSerializer,
                description="You are not the owner of this agreement.",
            ),
            404: OpenApiResponse(
                ErrorResponseSerializer,
                description="Agreement not found.",
            ),
        },
        summary="Sign a student loan bonding agreement",
        description=(
            "Records the student's signing timestamp and changes the "
            "agreement status to SIGNED. Only allowed while the status is "
            "GENERATED or PENDING_SIGNATURE. No request body is needed."
        ),
        tags=["Agreements"],
    )
    def post(self, request, agreement_number):
        try:
            agreement = Agreement.objects.get(
                agreement_number=agreement_number
            )
        except Agreement.DoesNotExist:
            return Response(
                {'error': 'Agreement not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        user = request.user

        if not user.is_staff and agreement.student_id not in [
            str(user.pk),
            user.get_username()
        ]:
            return Response(
                {'error': 'You are not authorized to sign this agreement.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if agreement.status not in [
            Agreement.Status.GENERATED,
            Agreement.Status.PENDING_SIGNATURE
        ]:
            return Response(
                {
                    'error': 'This agreement cannot be signed in its current status.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        agreement.student_signed_at = timezone.now()
        agreement.status = Agreement.Status.SIGNED

        agreement.save(
            update_fields=[
                'student_signed_at',
                'status',
                'updated_at'
            ]
        )

        serializer = AgreementSerializer(agreement)

        return Response(
            {
                'message': 'Agreement signing recorded successfully.',
                'agreement': serializer.data
            },
            status=status.HTTP_200_OK
        )


class AgreementCountersignView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        request=None,
        parameters=[AGREEMENT_NUMBER_PARAM],
        responses={
            200: AgreementActionResponseSerializer,
            400: OpenApiResponse(
                ErrorResponseSerializer,
                description="Agreement has not been signed by the student.",
            ),
            403: OpenApiResponse(
                description="Admin (staff) access is required.",
            ),
            404: OpenApiResponse(
                ErrorResponseSerializer,
                description="Agreement not found.",
            ),
        },
        summary="Countersign a student loan bonding agreement",
        description=(
            "Staff only. Records the board's countersigning timestamp and "
            "changes the agreement status to COUNTERSIGNED. Only allowed "
            "when the status is SIGNED. No request body is needed."
        ),
        tags=["Agreements"],
    )
    def post(self, request, agreement_number):
        try:
            agreement = Agreement.objects.get(
                agreement_number=agreement_number
            )
        except Agreement.DoesNotExist:
            return Response(
                {'error': 'Agreement not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if agreement.status != Agreement.Status.SIGNED:
            return Response(
                {
                    'error': 'Only student-signed agreements can be countersigned.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        agreement.board_countersigned_at = timezone.now()
        agreement.status = Agreement.Status.COUNTERSIGNED

        agreement.save(
            update_fields=[
                'board_countersigned_at',
                'status',
                'updated_at'
            ]
        )

        serializer = AgreementSerializer(agreement)

        return Response(
            {
                'message': 'Agreement countersigned successfully.',
                'agreement': serializer.data
            },
            status=status.HTTP_200_OK
        )