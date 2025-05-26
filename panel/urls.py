from django.urls import path

from .views.panel import panel_login, panel_index
from .views.samorzad import add_voting, samorzad_index


app_name = 'panel'

urlpatterns = [
    path('login/', panel_login, name='login'),
    path('index/', panel_index, name='index'),
    #Samorząd
    path('samorzad/', samorzad_index, name='samorzad_index'),
    path('samorzad/dodaj-glosowanie', add_voting, name='add_voting'),
]