from rest_framework import generics

from .models import Night
from .serializers import NightSerializer


class NightListView(generics.ListAPIView):
    """Every club's Nights, for a Player choosing which Nights to get notifications for.

    One Player account can play at any club (docs/DECISIONS.md), so this is not limited to
    one Club. Nights are a public schedule: no Club's private data is in them.
    """

    queryset = Night.objects.select_related("club")
    serializer_class = NightSerializer
