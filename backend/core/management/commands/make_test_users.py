"""Adds test users to clubs: `manage.py make_test_users "Club name" ...`.

One user per role (Admin, Referee, Player, Goalkeeper, Booking User) at each named Club,
with no password: only a superuser can sign in as them, from Profile, Log in as
(accounts/testers.py). Runs on any database, the live one too. Running it again brings the
users up to date, e.g. opting the Players into Nights added since.
"""

from django.core.management.base import BaseCommand, CommandError

from accounts.testers import make_test_users
from clubs.models import Club


class Command(BaseCommand):
    help = "Adds test users, one per role, that only a superuser can sign in as."

    def add_arguments(self, parser):
        parser.add_argument("clubs", nargs="+", help="Names of existing clubs.")

    def handle(self, *args, clubs, **options):
        found = {club.name: club for club in Club.objects.filter(name__in=clubs)}
        missing = [name for name in clubs if name not in found]
        if missing:
            raise CommandError(f"No club named: {', '.join(missing)}")
        for name in clubs:
            club = found[name]
            self.stdout.write(f"{club}:")
            for user in make_test_users(club):
                self.stdout.write(f"  {user.email:<32} {user.name}")
        self.stdout.write("A superuser signs in as them from Profile, Log in as.")
