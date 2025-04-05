from django.http import HttpRequest
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from django.db.models import Count, F
from django.utils import timezone
from datetime import timedelta
from ..models import Voting, Candidate, CandidateRegistration, Vote
from .serializers import VotingResultSerializer
from collections import defaultdict
import json
import pytz


class TokenObtainView(APIView):
    """
    Zwraca tokeny JWT dla zalogowanego użytkownika Azure
    """
    def post(self, request):
        user_id = request.session.get('microsoft_user_id')
        if not user_id:
            return Response(
                {"detail": "Użytkownik nie jest zalogowany"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        token = RefreshToken()
        token['user_id'] = user_id
        return Response({
            'refresh': str(token),
            'access': str(token.access_token),
        })

class VotingResultsChartAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, voting_id):
        try:
            voting = Voting.objects.get(pk=voting_id)
        except Voting.DoesNotExist:
            return Response(
                {"detail": "Głosowanie nie istnieje"},
                status=status.HTTP_404_NOT_FOUND
            )
        registrations = CandidateRegistration.objects.filter(
            voting=voting,
            is_eligible=True
        ).prefetch_related(
            'votes'
        ).select_related('candidate').annotate(
            votes_count=Count('votes')
        ).order_by('candidate__first_name', 'candidate__last_name')
        total_votes = Vote.objects.filter(
            candidate_registration__voting=voting
        ).count()
        results = []
        for reg in registrations:
            vote_dates = [vote.created_at.strftime('%Y-%m-%d %H:%M:%S') for vote in reg.votes.all()]
            percentage = (reg.votes_count / total_votes * 100) if total_votes > 0 else 0
            results.append({
                "candidate": reg.candidate,
                "votes_count": reg.votes_count,
                "percentage": round(percentage, 2),
                "vote_dates": vote_dates,
            })
        serializer = VotingResultSerializer(results, many=True)
        return Response(serializer.data)


class VotingTimelineChartAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, voting_id):
        try:
            voting = Voting.objects.get(pk=voting_id)
        except Voting.DoesNotExist:
            return Response({"error": "Voting not found"}, status=404)
        votes = Vote.objects.filter(
            candidate_registration__voting=voting
        ).select_related(
            'candidate_registration__candidate'
        ).order_by('created_at')
        timeline_data = {
            "timeline": [],
            "candidates": defaultdict(lambda: {"votes": [], "name": ""})
        }
        registrations = CandidateRegistration.objects.filter(
            voting=voting,
            is_eligible=True
        ).select_related('candidate')
        for reg in registrations:
            timeline_data["candidates"][reg.candidate.id]["name"] = \
                f"{reg.candidate.first_name} {reg.candidate.last_name}"
        vote_counts = defaultdict(int)
        for vote in votes:
            timestamp = vote.created_at.astimezone(
                pytz.timezone('Europe/Warsaw')
            ).strftime("%Y-%m-%d %H:%M:%S")
            if timestamp not in timeline_data["timeline"]:
                timeline_data["timeline"].append(timestamp)
            candidate_id = vote.candidate_registration.candidate.id
            vote_counts[candidate_id] += 1
            for cand_id in timeline_data["candidates"]:
                timeline_data["candidates"][cand_id]["votes"].append(
                    vote_counts.get(cand_id, 0)
                )
        if not timeline_data["timeline"]:
            for cand_id in timeline_data["candidates"]:
                timeline_data["candidates"][cand_id]["votes"] = []
        return Response(timeline_data)