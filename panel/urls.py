from django.urls import path

from .views.panel import panel_login, panel_index, actions_list_main, partial_actions_list_table
from .views.samorzad import (
    add_empty_voting,
    samorzad_index,
    samorzad_add_candidate,
    samorzad_add_candidature,
    partial_candidates_search,
    list_candidates,
    list_candidatures,
    #read_voting,
    update_voting,
    update_candidate,
    update_candidature,
    delete_voting,
    delete_candidate,
    delete_candidature,
    redirect_to_candidature,
)


app_name = 'panel'

urlpatterns = [
    path('login/', panel_login, name='login'),
    path('index/', panel_index, name='index'),
    path('akcje/', actions_list_main, name="list_actions_main"),
    path('akcje-lista', partial_actions_list_table, name='list_actions_table'),
    #Samorząd
    path('samorzad/dodaj-glosowanie-puste', add_empty_voting, name='samorzad_add_empty_voting'),
    path('samorzad/dodaj-kandydata', samorzad_add_candidate, name="samorzad_add_candidate"),
    path('samorzad/dodaj-kandydature', samorzad_add_candidature, name='samorzad_add_candidature'),
    path('samorzad/', samorzad_index, name='samorzad_index'),
    path('samorzad/lista-kandydatow', list_candidates, name='list_candidates'),
    path('samorzad/lista-kandydatur', list_candidatures, name="list_candidatures"),
    path('samorzad/glosowania/edytuj/<int:voting_id>', update_voting, name="update_voting"),
    path('samorzad/kandydaci/edytuj/<int:candidate_id>', update_candidate, name="update_candidate"),
    path('samorzad/kandydatury/edytuj/<int:candidature_id>', update_candidature, name="update_candidature"),
    path('samorzad/glosowania/usun', delete_voting, name="delete_voting"),
    path('samorzad/kandydaci/usun', delete_candidate, name="delete_candidate"),
    path('samorzad/kandydatury/usun', delete_candidature, name="delete_candidature"),
    path('samorzad/program-przekieruj/<int:electoral_program_id>', redirect_to_candidature, name="redirect_to_candidature"),
    # Partials
    path('samorzad/szukaj/kandydaci', partial_candidates_search, name='partial_candidates_search')
]