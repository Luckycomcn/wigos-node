import csv
import logging
from pathlib import Path

from django.db import migrations

logger = logging.getLogger(__name__)

wmo_members = []

# Read ISO3166.csv and populate wmo_members
# 路径基于本文件定位，而不是容器内的 /app —— 否则在宿主机/CI 里跑迁移会直接
# FileNotFoundError，`makemigrations --check` 和 `manage.py test` 都过不去。
_ISO3166 = Path(__file__).resolve().parent.parent / 'codelists' / 'ISO3166.csv'
with open(_ISO3166, 'r') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        # Assuming 'name' column for country name, adjust as needed
        name = row.get('rdfs:label', None)
        iso_code = row.get('skos:notation', None)
        if not name or not iso_code:
            logger.warning(f"Skipping row {i} due to missing data: {row}")
            continue  # Skip rows with missing data
        wmo_members.append((name, iso_code))


name_template = 'nfps_{}'  # Template for group names

def create_custom_groups(apps, schema_editor):
    # Use apps.get_model to avoid importing models directly
    #Group = apps.get_model('auth', 'Group')
    Group = apps.get_model('auth', 'Group')
    WIGOSNodeGroup = apps.get_model('api', 'WIGOSNodeGroup')
    Permission = apps.get_model('auth', 'Permission')

    for (name, iso_code) in wmo_members:

        # Create the group
        group, created = Group.objects.get_or_create(name=name_template.format(name))

        WIGOSNodeGroup.objects.update_or_create(
            group=group,
            defaults={"issuer_identifier": iso_code}
        )

        # Find and assign specific permissions
        try:
            # Example: targeting standard 'change' permission on a custom model
            can_edit_stations = Permission.objects.get(codename='change_station')
            group.permissions.add(can_edit_stations)
            can_add_stations = Permission.objects.get(codename='add_station')
            group.permissions.add(can_add_stations)
        except Permission.DoesNotExist:
            pass

def remove_custom_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for (name, iso_code) in wmo_members:
        Group.objects.filter(name=name_template.format(name)).delete()

class Migration(migrations.Migration):

    dependencies = [
        # Ensure it runs after your initial app migrations
        ('api', '0003_wigosnodegroup'),
    ]

    operations = [
        migrations.RunPython(create_custom_groups, reverse_code=remove_custom_groups),
    ]