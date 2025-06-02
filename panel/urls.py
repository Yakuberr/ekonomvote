from django.urls import path

from .views.panel import panel_login, panel_index
from .views.samorzad import (
    add_empty_voting,
    samorzad_index,
    samorzad_add_candidate,
    samorzad_add_candidature,
    partial_candidates_search
)


app_name = 'panel'

urlpatterns = [
    path('login/', panel_login, name='login'),
    path('index/', panel_index, name='index'),
    #Samorząd
    path('samorzad/', samorzad_index, name='samorzad_index'),
    path('samorzad/dodaj-glosowanie-puste', add_empty_voting, name='samorzad_add_empty_voting'),
    path('samorzad/dodaj-kandydata', samorzad_add_candidate, name="samorzad_add_candidate"),
    path('samorzad/dodaj-kandydature', samorzad_add_candidature, name='samorzad_add_candidature'),
    # Partials
    path('samorzad/szukaj/kandydaci', partial_candidates_search, name='partial_candidates_search')
]