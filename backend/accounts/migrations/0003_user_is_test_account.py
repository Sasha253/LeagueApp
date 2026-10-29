from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_club_invite"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_test_account",
            field=models.BooleanField(
                default=False, help_text="No password: only a superuser can sign in as this user."
            ),
        ),
    ]
