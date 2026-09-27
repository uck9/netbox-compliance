from django.db import migrations, models


def copy_tenant_to_tenants(apps, schema_editor):
    PackageAssignment = apps.get_model('netbox_compliance', 'PackageAssignment')
    for assignment in PackageAssignment.objects.exclude(tenant__isnull=True):
        assignment.tenants.add(assignment.tenant_id)


def copy_tenants_to_tenant(apps, schema_editor):
    PackageAssignment = apps.get_model('netbox_compliance', 'PackageAssignment')
    for assignment in PackageAssignment.objects.all():
        first = assignment.tenants.first()
        if first is not None:
            assignment.tenant = first
            assignment.save(update_fields=['tenant'])


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_compliance', '0007_packageassignment_tenant'),
        ('tenancy', '0001_squashed_0012'),
    ]

    operations = [
        migrations.AddField(
            model_name='packageassignment',
            name='tenants',
            field=models.ManyToManyField(
                blank=True,
                related_name='compliance_package_assignments',
                to='tenancy.tenant',
            ),
        ),
        migrations.RunPython(copy_tenant_to_tenants, copy_tenants_to_tenant),
        migrations.RemoveField(
            model_name='packageassignment',
            name='tenant',
        ),
    ]
