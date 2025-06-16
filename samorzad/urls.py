from django.urls import path
from . import views

app_name="samorzad"

urlpatterns = [
    path('', views.list_votings, name="index"),
    # API urls
    path('glosowania/timeline/<int:voting_id>', views.get_timeline_data, name="get_timeline_data"),
    path('glosowania/chart/<int:voting_id>', views.get_chart_data, name="get_chart_data"),
    path('glosowania/<int:voting_id>', views.get_voting_details, name='get_voting_details'),
    # PARTIALS
    path('glosowania/partial/zaladuj-glosowania', views.partial_list_old_votings, name="partial_list_old_votings")
]