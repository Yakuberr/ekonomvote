from django.urls import path
from . import views

app_name="samorzad"

urlpatterns = [
    path('', views.list_votings, name="index"),
    path('voting/<id>', views.get_voting_details, name='get_voting_details'),
    path('vote', views.post_vote, name="post_vote"),
]