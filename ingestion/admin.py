from django.contrib import admin
from .models import Tenant, IngestionBatch, EmissionRecord, AuditEvent


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']


@admin.register(IngestionBatch)
class IngestionBatchAdmin(admin.ModelAdmin):
    list_display = ['source_type', 'filename', 'status', 'row_count', 'error_count', 'uploaded_at']
    list_filter = ['source_type', 'status']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['activity_date', 'scope', 'category', 'raw_quantity', 'raw_unit', 'co2e_kg', 'status']
    list_filter = ['scope', 'category', 'status']
    search_fields = ['activity_description', 'source_entity', 'source_location']


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action', 'actor', 'record']
    list_filter = ['action']
    readonly_fields = ['id', 'record', 'action', 'actor', 'timestamp', 'detail']
