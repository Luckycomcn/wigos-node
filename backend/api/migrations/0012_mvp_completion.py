# MVP completion (F-6 / F-8 / F-19 / F-22 / F-24 + publishing records)
# Hand-written to match api/models.py; run `manage.py makemigrations --check`
# on a PostGIS-capable host to confirm no drift.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_auto_20260930_1030'),
    ]

    operations = [
        # F-19: soft-delete state on Station
        migrations.AddField(
            model_name='station',
            name='archived',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name='station',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # F-8: version history
        migrations.CreateModel(
            name='StationVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('wmdrv2', models.JSONField()),
                ('operation', models.CharField(default='create', max_length=16)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='station_versions', to=settings.AUTH_USER_MODEL)),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='api.station')),
            ],
            options={
                'ordering': ['-version'],
                'unique_together': {('station', 'version')},
            },
        ),
        # F-6: groups / clusters
        migrations.CreateModel(
            name='StationGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('description', models.TextField(blank=True, default='')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='station_groups', to=settings.AUTH_USER_MODEL)),
                ('stations', models.ManyToManyField(blank=True, related_name='groups', to='api.station')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        # F-22: templates
        migrations.CreateModel(
            name='StationTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('payload', models.JSONField()),
                ('shared', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='station_templates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('owner', 'name')},
            },
        ),
        # F-24: grades
        migrations.CreateModel(
            name='StationGrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=64, unique=True)),
                ('label', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('criteria', models.JSONField(default=list)),
                ('order', models.IntegerField(default=100)),
            ],
            options={
                'ordering': ['order', 'code'],
            },
        ),
        # publishing records (WNM)
        migrations.CreateModel(
            name='PublishedRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(max_length=128)),
                ('wnm', models.JSONField()),
                ('url', models.URLField(max_length=1024)),
                ('operation', models.CharField(default='canonical', max_length=16)),
                ('published', models.DateTimeField(auto_now_add=True)),
                ('published_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='publications', to=settings.AUTH_USER_MODEL)),
                ('station', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='publications', to='api.station')),
            ],
            options={
                'ordering': ['-published'],
            },
        ),
    ]
