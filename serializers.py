from rest_framework import serializers


class GeographicalDataSerializer(serializers.Serializer):
    country__name = serializers.CharField(read_only=True)
    country_count = serializers.IntegerField(read_only=True)