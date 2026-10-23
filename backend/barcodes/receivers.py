"""Issues a Team's Payment Barcode when it is paid (FR-20, PRD "Barcode authorisation")."""

from django.dispatch import receiver

from payments.signals import team_paid

from . import services


@receiver(team_paid, dispatch_uid="barcodes-issue-on-payment")
def issue_barcode(sender, team, **kwargs) -> None:
    services.issue_on_payment(team)
