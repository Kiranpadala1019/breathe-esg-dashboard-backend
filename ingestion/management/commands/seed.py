from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from ingestion.models import Tenant


class Command(BaseCommand):
    help = 'Seed demo tenant and analyst user'

    def handle(self, *args, **kwargs):
        tenant, created = Tenant.objects.get_or_create(
            id='00000000-0000-0000-0000-000000000001',
            defaults={'name': 'Acme Corp Demo', 'slug': 'acme-demo'},
        )
        user, _ = User.objects.get_or_create(
            username='analyst',
            defaults={'email': 'analyst@acme.com', 'is_staff': True},
        )
        user.set_password('analyst123')
        user.save()
        self.stdout.write(f'Tenant: {tenant.name} (id: {tenant.id})')
        self.stdout.write('Analyst user: analyst / analyst123')
