from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count, Sum, Q

from .models import Tenant, IngestionBatch, EmissionRecord, AuditEvent
from .serializers import (
    TenantSerializer, IngestionBatchSerializer,
    EmissionRecordSerializer, AuditEventSerializer,
)
from .parsers.sap_parser     import parse_sap_flat_file
from .parsers.utility_parser import parse_utility_csv
from .parsers.travel_parser  import parse_travel_csv


PARSER_MAP = {
    'SAP':     parse_sap_flat_file,
    'UTILITY': parse_utility_csv,
    'TRAVEL':  parse_travel_csv,
}


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class IngestionBatchViewSet(viewsets.ModelViewSet):
    queryset = IngestionBatch.objects.all().order_by('-uploaded_at')
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs


class EmissionRecordViewSet(viewsets.ModelViewSet):
    queryset = EmissionRecord.objects.select_related('batch', 'tenant').all()
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if params.get('tenant'):
            qs = qs.filter(tenant_id=params['tenant'])
        if params.get('status'):
            qs = qs.filter(status=params['status'])
        if params.get('scope'):
            qs = qs.filter(scope=params['scope'])
        if params.get('batch'):
            qs = qs.filter(batch_id=params['batch'])
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        record = self.get_object()
        if record.status == 'LOCKED':
            return Response({'error': 'Record is locked for audit'}, status=400)
        note = request.data.get('note', '')
        record.status = 'APPROVED'
        record.analyst_note = note
        record.reviewed_at = timezone.now()
        record.save()
        _log_event(record, 'APPROVED', request.user, {'note': note})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        record = self.get_object()
        if record.status == 'LOCKED':
            return Response({'error': 'Record is locked for audit'}, status=400)
        reason = request.data.get('reason', '')
        record.status = 'REJECTED'
        record.analyst_note = reason
        record.reviewed_at = timezone.now()
        record.save()
        _log_event(record, 'REJECTED', request.user, {'reason': reason})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        record = self.get_object()
        if record.status != 'APPROVED':
            return Response({'error': 'Only approved records can be locked'}, status=400)
        record.status = 'LOCKED'
        record.locked_at = timezone.now()
        record.save()
        _log_event(record, 'LOCKED', request.user, {})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['patch'])
    def edit(self, request, pk=None):
        record = self.get_object()
        if record.status == 'LOCKED':
            return Response({'error': 'Record is locked'}, status=400)
        before = {
            'raw_quantity': str(record.raw_quantity),
            'raw_unit': record.raw_unit,
            'co2e_kg': str(record.co2e_kg),
            'analyst_note': record.analyst_note,
        }
        allowed_fields = ['raw_quantity', 'raw_unit', 'co2e_kg', 'analyst_note', 'activity_description']
        for field in allowed_fields:
            if field in request.data:
                setattr(record, field, request.data[field])
        record.is_edited = True
        record.save()
        after = {f: str(getattr(record, f)) for f in allowed_fields if f in before}
        _log_event(record, 'EDITED', request.user, {'before': before, 'after': after})
        return Response(EmissionRecordSerializer(record).data)

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        record = self.get_object()
        events = AuditEvent.objects.filter(record=record)
        return Response(AuditEventSerializer(events, many=True).data)


@api_view(['POST'])
def ingest_file(request):
    """
    POST /api/ingest/
    Multipart form: file, source_type (SAP|UTILITY|TRAVEL), tenant_id
    """
    source_type = request.data.get('source_type', '').upper()
    tenant_id   = request.data.get('tenant_id')
    file_obj    = request.FILES.get('file')

    if source_type not in PARSER_MAP:
        return Response({'error': f'Invalid source_type. Choose from: {list(PARSER_MAP.keys())}'}, status=400)
    if not tenant_id:
        return Response({'error': 'tenant_id required'}, status=400)
    if not file_obj:
        return Response({'error': 'No file uploaded'}, status=400)

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return Response({'error': 'Tenant not found'}, status=404)

    # Get or create a demo analyst user
    analyst, _ = User.objects.get_or_create(username='analyst', defaults={'is_staff': True})

    batch = IngestionBatch.objects.create(
        tenant=tenant,
        source_type=source_type,
        filename=file_obj.name,
        uploaded_by=analyst,
        status='PROCESSING',
    )

    try:
        file_bytes = file_obj.read()
        parser = PARSER_MAP[source_type]
        result = parser(file_bytes)

        created = []
        for rec_data in result['records']:
            rec = EmissionRecord.objects.create(
                tenant=tenant,
                batch=batch,
                **rec_data,
            )
            _log_event(rec, 'INGESTED', analyst, {'source': source_type})
            if rec.status == 'FLAGGED':
                _log_event(rec, 'FLAGGED', analyst, {'reason': rec.flag_reason})
            created.append(str(rec.id))

        batch.status = 'COMPLETE'
        batch.row_count = len(created)
        batch.error_count = len(result['errors'])
        batch.raw_metadata = result['metadata']
        batch.save()

        return Response({
            'batch_id': str(batch.id),
            'records_created': len(created),
            'errors': result['errors'],
            'metadata': result['metadata'],
        }, status=201)

    except Exception as e:
        batch.status = 'FAILED'
        batch.save()
        return Response({'error': str(e), 'batch_id': str(batch.id)}, status=500)


@api_view(['GET'])
def dashboard_summary(request):
    tenant_id = request.query_params.get('tenant')
    qs = EmissionRecord.objects.all()
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    total_co2e = qs.aggregate(total=Sum('co2e_kg'))['total'] or 0
    by_status = dict(qs.values_list('status').annotate(count=Count('id')))
    by_scope  = dict(qs.values_list('scope').annotate(count=Count('id')))
    by_scope_co2e = {
        str(row['scope']): float(row['total'] or 0)
        for row in qs.values('scope').annotate(total=Sum('co2e_kg'))
    }

    return Response({
        'total_records': qs.count(),
        'total_co2e_kg': float(total_co2e),
        'by_status': by_status,
        'by_scope': by_scope,
        'by_scope_co2e': by_scope_co2e,
        'pending_count':  by_status.get('PENDING', 0),
        'flagged_count':  by_status.get('FLAGGED', 0),
        'approved_count': by_status.get('APPROVED', 0),
    })


def _log_event(record, action, user, detail):
    AuditEvent.objects.create(record=record, action=action, actor=user, detail=detail)
