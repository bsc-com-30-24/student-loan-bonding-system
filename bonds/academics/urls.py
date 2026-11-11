from rest_framework.routers import SimpleRouter

from .views import AcademicYearViewSet

router = SimpleRouter()
router.register("academic-years", AcademicYearViewSet, basename="academic-year")

urlpatterns = router.urls