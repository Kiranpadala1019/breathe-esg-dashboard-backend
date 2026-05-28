from rest_framework import serializers
from .models import Tenant, IngestionBatch, EmissionRecord, AuditEvent


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'


class IngestionBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionBatch
        fields = '__all__'


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display    = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    batch_filename   = serializers.CharField(source='batch.filename', read_only=True)

    class Meta:
        model = EmissionRecord
        fields = '__all__'


class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.username', read_only=True)

    class Meta:
        model = AuditEvent
        fields = '__all__'
