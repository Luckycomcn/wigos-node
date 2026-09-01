from django.db import migrations


wmo_members = [('Switzerland', 0), ('Germany', 1), ('France', 2)] # for testing

name_template = 'nfps_{}'  # Template for group names

def create_custom_groups(apps, schema_editor):
    # Use apps.get_model to avoid importing models directly
    #Group = apps.get_model('auth', 'Group')
    WIGOSNodeGroup = apps.get_model('api', 'WIGOSNodeGroup')
    Permission = apps.get_model('auth', 'Permission')

    for (member_name, issuer_identifier) in wmo_members:

        # Create the group
        manager_group, created = WIGOSNodeGroup.objects.get_or_create(name=name_template.format(member_name), issuer_identifier=issuer_identifier)
        
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
    WIGOSNodeGroup = apps.get_model('api', 'WIGOSNodeGroup')
    for (member_name, issuer_identifier) in wmo_members:
        WIGOSNodeGroup.objects.filter(name=name_template.format(member_name), issuer_identifier=issuer_identifier).delete()

class Migration(migrations.Migration):

    dependencies = [
        # Ensure it runs after your initial app migrations
        ('api', '0003_station_owner'),
    ]

    operations = [
        migrations.RunPython(create_custom_groups, reverse_code=remove_custom_groups),
    ]