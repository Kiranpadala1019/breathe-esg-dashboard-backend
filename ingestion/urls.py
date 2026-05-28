from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('tenants',  views.TenantViewSet)
router.register('batches',  views.IngestionBatchViewSet)
router.register('records',  views.EmissionRecordViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('ingest/',    views.ingest_file,        name='ingest'),
    path('dashboard/', views.dashboard_summary,  name='dashboard'),
]
