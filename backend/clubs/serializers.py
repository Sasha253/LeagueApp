from rest_framework import serializers

from .models import Club, Night


class ClubSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Club
        fields = ["id", "name"]


class NightSerializer(serializers.ModelSerializer):
    club = ClubSummarySerializer(read_only=True)

    class Meta:
        model = Night
        fields = ["id", "club", "weekday"]
