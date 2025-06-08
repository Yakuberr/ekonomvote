from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpRequest, HttpResponseNotAllowed
from django.shortcuts import redirect, render, reverse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from django.contrib.postgres.search import SearchRank, SearchQuery, SearchVector, TrigramSimilarity

import pytz
from rest_framework.exceptions import ValidationError

from samorzad.models import Voting, Candidate, CandidateRegistration
from panel.forms import SamorzadAddEmptyVotingForm, SamorzadAddCandidateForm, CandidateRegistrationForm, ElectoralProgramFormSet

# CREATE views
# TODO: Walidcja czy id danego obiektu w bazie danych istnieje

@require_http_methods(['GET', 'POST'])
def add_empty_voting(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    if request.method == 'GET':
        form = SamorzadAddEmptyVotingForm()
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={})
    if request.method == 'POST':
        form = SamorzadAddEmptyVotingForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Puste głosowanie dodano pomyślnie')
            return redirect(reverse('panel:samorzad_index'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:samorzad_add_empty_voting'))
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={})

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
def samorzad_add_candidate(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    if request.method == 'GET':
        form = SamorzadAddCandidateForm()
        return render(request, 'panel/samorzad/samorzad_add_candidate.html', context={
            'form':form
        })
    if request.method == 'POST':
        form = SamorzadAddCandidateForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dodano pomyślnie nowego kandydata')
            return redirect(reverse('panel:samorzad_index'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:samorzad_add_candidate'))

@require_http_methods(["GET", 'POST'])
@login_required(login_url='office_auth:microsoft_login')
def samorzad_add_candidature(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    if request.method == 'GET':
        form = CandidateRegistrationForm()
        formset = ElectoralProgramFormSet()
        votings = Voting.objects.filter(planned_start__gt=timezone.now()).order_by('planned_start')
        return render(request, 'panel/samorzad/samorzad_add_candidature.html', context={
            'votings':votings
        })
    if request.method == 'POST':
        form = CandidateRegistrationForm(request.POST)
        formset = ElectoralProgramFormSet(request.POST)
        if form.is_valid():
            candidate_reg = form.save()
            formset = ElectoralProgramFormSet(request.POST, instance=candidate_reg)
            if formset.is_valid():
                formset.save()
                messages.success(request, "Pomyślnie dodano kandydature")
                return redirect(reverse('panel:samorzad_add_candidature'))
            else:
                for i, form_errors in enumerate(formset.errors):
                    for field, errors in form_errors.items():
                        for error in errors:
                            messages.error(request, f"Błąd. Upewnij się że program wyborczy nie jest pusty. {error}")
                return redirect(reverse('panel:samorzad_add_candidature'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
                    return redirect(reverse('panel:samorzad_add_candidature'))


@require_http_methods(["GET"])
@login_required(login_url='office_auth:microsoft_login')
def partial_candidates_search(request:HttpRequest):
    query = request.GET.get('search', '')
    if query == '':
        return render(request, 'panel/samorzad/partials/candidates_select.html', context={
            'candidates':[]
        })
    vector = SearchVector('first_name', 'second_name', 'last_name')
    query = SearchQuery(query, search_type='plain')
    candidates = Candidate.objects.annotate(rank=SearchRank(vector, query)).filter(rank__gte=0.03).order_by('-rank')
    return render(request, 'panel/samorzad/partials/candidates_select.html', context={
        'candidates': candidates
    })

# READ views

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
def samorzad_index(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    sort_by = request.GET.get('sort', 'planned_start')
    order = request.GET.get('order', 'desc')
    allowed_sort_fields = ['planned_start', 'planned_end', 'created_at', 'updated_at']
    if sort_by not in allowed_sort_fields:
        sort_by = 'planned_start'
    if order not in ['asc', 'desc']:
        order = 'desc'
    if order == 'desc':
        order_by = f'-{sort_by}'
    else:
        order_by = sort_by
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    votings = Voting.objects.prefetch_related('candidate_registrations').order_by(order_by)
    paginator = Paginator(votings, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    return render(request, 'panel/samorzad/samorzad_index.html', context={
        'page_obj':page_obj,
        'current_sort': sort_by,
        'current_order': order,
        'allowed_fields': allowed_sort_fields
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
def list_candidates(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    SORT_MAP = {
        'name': ['first_name', 'second_name', 'last_name'],
        'created_at': ['created_at'],
        'updated_at': ['updated_at'],
    }
    sort_by = request.GET.get('sort', 'name')
    order = request.GET.get('order', 'asc')
    allowed_sort_fields = SORT_MAP.keys()
    if sort_by not in allowed_sort_fields:
        sort_by = 'name'
    if order not in ['asc', 'desc']:
        order = 'asc'
    sort_fields = SORT_MAP[sort_by]
    if order == 'desc':
        sort_fields = [f'-{field}' for field in sort_fields]
    query = request.GET.get('search')
    if query is None or query == '':
        candidates = Candidate.objects.all().order_by(*sort_fields)
        query = ''
    else:
        vector = SearchVector('first_name', 'second_name', 'last_name')
        search = SearchQuery(query, search_type='plain')
        candidates = Candidate.objects.annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_fields)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(candidates, 20)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    return render(request, 'panel/samorzad/candidates_list.html', context={
        'page_obj':page_obj,
        'query':query,
        'current_sort': sort_by,
        'current_order': order,
        'allowed_fields': allowed_sort_fields
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
def list_candidatures(request:HttpRequest):
    if not request.user.is_superuser:
        return redirect(reverse('panel:login'))
    query = request.GET.get('search')
    SORT_MAP = {
        'name': ['candidate__first_name', 'candidate__second_name', 'candidate__last_name'],
        'planned_start': ['voting__planned_start'],
        'created_at': ['created_at'],
        'updated_at': ['updated_at'],
    }
    sort_by = request.GET.get('sort', 'name')
    order = request.GET.get('order', 'asc')
    allowed_sort_fields = SORT_MAP.keys()
    if sort_by not in allowed_sort_fields:
        sort_by = 'name'
    if order not in ['asc', 'desc']:
        order = 'asc'
    sort_fields = SORT_MAP[sort_by]
    if order == 'desc':
        sort_fields = [f'-{field}' for field in sort_fields]
    if query is None or query == '':
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').order_by(*sort_fields)
        query = ''
    else:
        vector = SearchVector('candidate__first_name', 'candidate__second_name', 'candidate__last_name')
        search = SearchQuery(query, search_type='plain')
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_fields)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(candidatures, 20)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    return render(request, 'panel/samorzad/candidatures_list.html', context={
        'page_obj':page_obj,
        'query':query,
        'current_sort': sort_by,
        'current_order': order,
        'allowed_fields': allowed_sort_fields
    })




