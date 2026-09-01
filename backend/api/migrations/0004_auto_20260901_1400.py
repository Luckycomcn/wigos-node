from django.db import migrations


wmo_members = [('Switzerland', 0), ('Germany', 1), ('France', 2)] # for testing

name_template = 'nfps_{}'  # Template for group names

def create_custom_groups(apps, schema_editor):
    # Use apps.get_model to avoid importing models directly
    #Group = apps.get_model('auth', 'Group')
    Group = apps.get_model('auth', 'Group')
    WIGOSNodeGroup = apps.get_model('api', 'WIGOSNodeGroup')
    Permission = apps.get_model('auth', 'Permission')

    for (member_name, issuer_identifier) in wmo_members:

        # Create the group
        group, created = Group.objects.get_or_create(name=name_template.format(member_name))

        WIGOSNodeGroup.objects.update_or_create(
            group=group,
            defaults={"issuer_identifier": issuer_identifier}
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
    for (member_name, issuer_identifier) in wmo_members:
        Group.objects.filter(name=name_template.format(member_name)).delete()

class Migration(migrations.Migration):

    dependencies = [
        # Ensure it runs after your initial app migrations
        ('api', '0003_wigosnodegroup'),
    ]

    operations = [
        migrations.RunPython(create_custom_groups, reverse_code=remove_custom_groups),
    ]