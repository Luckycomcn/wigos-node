from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("outbox", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="publicationevent",
            name="needs_cleanup",
            field=models.BooleanField(default=False),
        ),
    ]
