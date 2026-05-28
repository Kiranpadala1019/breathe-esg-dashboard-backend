from django.db import models
from django.contrib.auth.models import User
import uuid


class Tenant(models.Model):
    """Multi-tenant support. Each enterprise client = one Tenant."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class IngestionBatch(models.Model):
    """
    One upload session = one batch. Tracks provenance at the batch level.
    All EmissionRecords link back here so we always know:
    - Which file produced this row
    - When it was ingested
    - Which source system
    """
    SOURCE_TYPES = [
        ('SAP', 'SAP Export'),
        ('UTILITY', 'Utility Portal CSV'),
        ('TRAVEL', 'Corporate Travel Export'),
    ]
    STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('COMPLETE', 'Complete'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    filename = models.CharField(max_length=500)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    raw_metadata = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.source_type} | {self.filename} | {self.uploaded_at.date()}"


class EmissionRecord(models.Model):
    """
    Core normalized record. One row of emission-producing activity.

    Design decision: we store BOTH the raw value/unit AND the normalized value in kgCO2e.
    This means we can re-normalize if emission factors update, and auditors can
    trace back to the original number.
    """
    SCOPE_CHOICES = [
        (1, 'Scope 1 — Direct'),
        (2, 'Scope 2 — Indirect Electricity'),
        (3, 'Scope 3 — Value Chain'),
    ]
    CATEGORY_CHOICES = [
        # Scope 1
        ('FUEL_STATIONARY', 'Stationary Combustion'),
        ('FUEL_MOBILE', 'Mobile Combustion'),
        # Scope 2
        ('ELECTRICITY', 'Purchased Electricity'),
        # Scope 3
        ('TRAVEL_AIR', 'Business Travel — Air'),
        ('TRAVEL_HOTEL', 'Business Travel — Hotel'),
        ('TRAVEL_GROUND', 'Business Travel — Ground'),
        ('PROCUREMENT', 'Purchased Goods & Services'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('FLAGGED', 'Flagged — Needs Attention'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('LOCKED', 'Locked for Audit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='records')
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='records')

    # --- Classification ---
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)

    # --- Activity Data (raw, as ingested) ---
    activity_date = models.DateField()
    activity_description = models.TextField(blank=True)
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    raw_unit = models.CharField(max_length=50)
    raw_source_row = models.JSONField(default=dict)

    # --- Normalized Values ---
    quantity_kwh = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    emission_factor_used = models.CharField(max_length=255, blank=True)
    emission_factor_source = models.CharField(max_length=255, blank=True)

    # --- Source Tracking ---
    source_location = models.CharField(max_length=500, blank=True)
    source_entity = models.CharField(max_length=500, blank=True)

    # --- Review Workflow ---
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    flag_reason = models.TextField(blank=True)
    analyst_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)

    # --- Audit Trail ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ['-activity_date']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'scope']),
            models.Index(fields=['batch']),
            models.Index(fields=['activity_date']),
        ]


class AuditEvent(models.Model):
    """
    Immutable log. Every status change, edit, approval is written here.
    Never deleted, never updated — append only.
    """
    ACTION_CHOICES = [
        ('INGESTED', 'Record Ingested'),
        ('FLAGGED', 'Auto-Flagged'),
        ('APPROVED', 'Approved by Analyst'),
        ('REJECTED', 'Rejected'),
        ('EDITED', 'Field Edited'),
        ('LOCKED', 'Locked for Audit'),
        ('NOTE_ADDED', 'Note Added'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_events')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    detail = models.JSONField(default=dict)

    class Meta:
        ordering = ['timestamp']
