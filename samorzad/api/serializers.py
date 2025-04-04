# api/serializers.py
from rest_framework import serializers
from ..models import Candidate, CandidateRegistration

class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'first_name', 'last_name', 'image']

class VotingResultSerializer(serializers.Serializer):
    candidate = CandidateSerializer()
    votes_count = serializers.IntegerField()
    percentage = serializers.FloatField()