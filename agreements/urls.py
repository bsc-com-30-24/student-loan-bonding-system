from django.urls import path

from .views import (
    AgreementListView,
    AgreementDetailView,
    AgreementGenerateView,
    AgreementSignView,
    AgreementCountersignView,
    AgreementPDFDownloadView,
)

urlpatterns = [
    path(
        '',
        AgreementListView.as_view(),
        name='agreement-list'
    ),
    path(
        'generate/',
        AgreementGenerateView.as_view(),
        name='agreement-generate'
    ),
    path(
        '<uuid:agreement_number>/sign/',
        AgreementSignView.as_view(),
        name='agreement-sign'
    ),
    path(
        '<uuid:agreement_number>/countersign/',
        AgreementCountersignView.as_view(),
        name='agreement-countersign'
    ),
    path(
        '<uuid:agreement_number>/download/',
        AgreementPDFDownloadView.as_view(),
        name='agreement-download'
    ),
    path(
        '<uuid:agreement_number>/',
        AgreementDetailView.as_view(),
        name='agreement-detail'
    ),
]