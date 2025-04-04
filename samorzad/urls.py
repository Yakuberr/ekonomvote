from django.urls import path
from . import views
from .api.views import VotingResultsChartAPIView, VotingTimelineChartAPI

app_name="samorzad"

urlpatterns = [
    path('', views.list_votings, name="index"),
    path('voting/<int:id>/', views.get_voting_details, name='get_voting_details'),
    path('vote', views.post_vote, name="post_vote"),
    # API urls
    path('votings/<int:voting_id>/results/', VotingResultsChartAPIView.as_view(), name='voting-results'),
    path('votings/<int:voting_id>/timeline/', VotingTimelineChartAPI.as_view(), name='voting-timeline'),
]