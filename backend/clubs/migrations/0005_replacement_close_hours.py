"""When one Team is out, how long the slot is offered to other Teams (FR-15, chunk 14).

Existing settings (every Club's, and the defaults for new Clubs) start at 2 hours before
kick-off (provisional, docs/OPEN_QUESTIONS.md "Chunk 14"). After this it is data.
"""

from django.db import migrations, models

HELP = (
    "When one Team is out, the slot is offered to other Teams until this many hours "
    "before kick-off (FR-15). Fewer than the readiness hours."
)


class Migration(migrations.Migration):
    dependencies = [("clubs", "0004_division_max_teams")]

    operations = [
        migrations.AddField(
            model_name="clubsettings",
            name="replacement_close_hours_before",
            field=models.PositiveSmallIntegerField(default=2, help_text=HELP),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="settingsdefaults",
            name="replacement_close_hours_before",
            field=models.PositiveSmallIntegerField(default=2, help_text=HELP),
            preserve_default=False,
        ),
    ]
