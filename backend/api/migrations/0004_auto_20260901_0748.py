from django.db import migrations

wmo_members = ['Switzerland','Germany', 'France'] # for testing

name_template = 'nfps_{}'  # Template for group names

def create_custom_groups(apps, schema_editor):
    # Use apps.get_model to avoid importing models directly
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')


    for member in wmo_members:

        # Create the group
        manager_group, created = Group.objects.get_or_create(name=name_template.format(member))
        
        # Find and assign specific permissions
        try:
            # Example: targeting standard 'change' permission on a custom model
            can_edit_stations = Permission.objects.get(codename='change_station')
            manager_group.permissions.add(can_edit_stations)
            can_add_stations = Permission.objects.get(codename='add_station')
            manager_group.permissions.add(can_add_stations)
        except Permission.DoesNotExist:
            pass

def remove_custom_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for member in wmo_members:
        Group.objects.filter(name=name_template.format(member)).delete()

class Migration(migrations.Migration):

    dependencies = [
        # Ensure it runs after your initial app migrations
        ('api', '0003_station_owner'),
    ]

    operations = [
        migrations.RunPython(create_custom_groups, reverse_code=remove_custom_groups),
    ]