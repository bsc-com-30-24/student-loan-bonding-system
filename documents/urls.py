cat > documents/urls.py <<'EOF'
from django.urls import path
from . import views

urlpatterns = [
    path("submit/", views.submit_document, name="submit_document"),
]
EOF