from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpRequest, HttpResponseNotAllowed
from django.shortcuts import redirect, render, reverse
from django.core.paginator import Paginator

from samorzad.models import Voting

def add_voting(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    if request.method == 'GET':
        return render(request, 'samorzad/samorzad_base.html', context={})

@login_required(login_url='office_auth:microsoft_login')
def samorzad_index(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    if request.method != 'GET':
        return HttpResponseNotAllowed(permitted_methods=['GET'])
    # TODO: Fajnie jakby było paginowane
    page_number = int(request.GET.get('page', 1))
    votings = Voting.objects.all().order_by('-planned_start')
    paginator = Paginator(votings, 5)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    page_obj.number
    return render(request, 'samorzad/samorzad_index.html', context={'page_obj':page_obj})

# TODO: Widok dodania pełnego głosowania
# TODO: Widok dodania kandydata
# TODO: Widok dodania programu wyborczego
# TODO: Widok dodania kandydatury
# TODO: Widok dodania pustego głosowania
# TODO: dekorator dla widoku, który sprawdza czy w sesji znajduje się microsoft_user_id
