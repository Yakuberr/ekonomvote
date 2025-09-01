from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.messages import SUCCESS
from django.http import HttpResponseForbidden, HttpRequest, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import redirect, render, reverse, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from django.contrib.postgres.search import SearchRank, SearchQuery, SearchVector, TrigramSimilarity
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Case, When, Value, CharField
from django.template.loader import render_to_string
from django.contrib.messages.constants import ERROR, SUCCESS, WARNING, INFO

import pytz
from urllib.parse import urlencode

from samorzad.models import Voting, Candidate, CandidateRegistration, ElectoralProgram
from panel.forms import (SamorzadAddEmptyVotingForm,
                         SamorzadAddCandidateForm,
                         CandidateRegistrationForm,
                         ElectoralProgramForm,
                         ListVotingsForm,
                         ListCandidatesForm,
                         ListCandidaturesForm)
from office_auth.auth_utils import opiekun_required
from office_auth.models import ActionLog
from .utils import get_changed_fields, build_sort_list, build_filter_kwargs, build_delete_feedback_response

def _create_voting_status(voting:Voting):
    if voting.planned_start <= timezone.now() and voting.planned_end >= timezone.now():
        return 'Aktywne'
    elif voting.planned_end > timezone.now():
        return 'Zaplanowane'
    else:return 'Zakończone'


# CREATE views

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def add_empty_voting(request:HttpRequest):
    """Widok tworzenia głosowania"""
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Pola z datami muszą wskazywać na przyszłe daty',
            'Wartość głosów do oddania musi być większa niż 0'
        ]
        form = SamorzadAddEmptyVotingForm()
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form': form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = SamorzadAddEmptyVotingForm(request.POST)
        if form.is_valid():
            try:
                voting = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_empty_voting'))
            except Exception as Ex:
                messages.error(request, message="Nie udało się dodać głosowania", extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_empty_voting'))
            messages.success(request, f'Dodano pomyślnie nowe głosowanie o ID: {voting.id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_index'),
                'add_new':reverse('panel:samorzad_add_empty_voting'),
                'edit':reverse('panel:update_voting', kwargs={'voting_id':voting.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            return redirect(reverse('panel:samorzad_add_empty_voting'))

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def samorzad_add_candidate(request:HttpRequest):
    """Widok tworzenia kandydata"""
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Klasa musi mieć wartość w formacie: "numer nazwa" np: 4 TI',
        ]
        form = SamorzadAddCandidateForm()
        return render(request, 'panel/samorzad/samorzad_add_candidate.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = SamorzadAddCandidateForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                candidate = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_candidate'))
            except Exception as Ex:
                messages.error(request, message="Nie udało się dodać kandydata", extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_candidate'))
            messages.success(request, f'Dodano pomyślnie nowego kandydata {candidate.first_name} {candidate.second_name} {candidate.last_name}, ID: {candidate.id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidates'),
                'add_new':reverse('panel:samorzad_add_candidate'),
                'edit':reverse('panel:update_candidate', kwargs={'candidate_id':candidate.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            return redirect(reverse('panel:samorzad_add_candidate'))

@require_http_methods(["GET", 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def samorzad_add_candidature(request:HttpRequest):
    """Widok tworzenia kandydatury"""
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Kandydat może mieć tylko jedną kandydaturę w ramach 1 głosowania',
            "Można wybrac tylko przyszłe głosowania"
        ]
        candidature_form = CandidateRegistrationForm()
        electoral_form = ElectoralProgramForm()
        votings = Voting.objects.filter(planned_start__gt=timezone.now()).order_by('planned_start')
        return render(request, 'panel/samorzad/samorzad_add_candidature.html', context={
            'votings':votings,
            'candidature_form':candidature_form,
            'electoral_form':electoral_form,
            'candidate_id':None,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        candidature_form = CandidateRegistrationForm(request.POST)
        electoral_form = ElectoralProgramForm(request.POST)
        if candidature_form.is_valid() and electoral_form.is_valid():
            try:
                with transaction.atomic():
                    candidature = candidature_form.save()
                    program = electoral_form.save(commit=False)
                    program.candidature = candidature
                    program.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_candidature'))
            except Exception as Ex:
                messages.error(request, message='Nie udało się dodać kandydatury', extra_tags='danger')
                return redirect(reverse('panel:samorzad_add_candidature'))
            messages.success(request, f'Dodano pomyślnie nową kandydaturę od ID: {candidature.id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_list_candidatures'),
                'add_new':reverse('panel:samorzad_add_candidature'),
                'edit':reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in candidature_form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            for field, errors in electoral_form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            return redirect(reverse('panel:samorzad_add_candidature'))


@require_http_methods(["GET"])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_candidates_search(request:HttpRequest):
    """Widok typu partial do wyszukiwania kandydatów"""
    query = request.GET.get('search', '')
    candidate_id = request.GET.get('candidate_id')
    if candidate_id is None:
        selected_candidate = None
    elif not candidate_id.isdigit:
        raise ValidationError("candidate_id nie jest liczbą całkowitą ")
    if query == '':
        selected_candidate = Candidate.objects.filter(id=candidate_id).first()
        return render(request, 'panel/samorzad/partials/candidates_select.html', context={
            'candidates':[],
            'selected_candidate':selected_candidate
        })
    vector = SearchVector('first_name', 'second_name', 'last_name')
    query = SearchQuery(query, search_type='plain')
    candidates = Candidate.objects.annotate(rank=SearchRank(vector, query)).filter(rank__gte=0.03).order_by('-rank')
    return render(request, 'panel/samorzad/partials/candidates_select.html', context={
        'candidates': candidates,
        'selected_candidate':None
    })

# READ views

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def samorzad_index(request:HttpRequest):
    """Widok głównego szablonu listy głosowań"""
    form = ListVotingsForm()
    status_list = ['Aktywne', 'Zaplanowane', 'Zakończone']
    return render(request, 'panel/samorzad/samorzad_index.html', context={
        'form': form,
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_read_voting_list(request:HttpRequest):
    """Widok listy z danymi głosowań"""
    SORT_MAP = {
        'start':['planned_start'],
        'end':['planned_end'],
        'creation':['created_at'],
        'update':['updated_at'],
        'id':['id']
    }
    FILTER_MAP = {
        'voting_status': {
            'field': 'status__in',
        },
    }
    form = ListVotingsForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    filter_kwargs = build_filter_kwargs(FILTER_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    votings = Voting.objects.prefetch_related('candidate_registrations').order_by(*sort_data['sort_fields'])
    votings = votings.annotate(
        status=Case(
            When(planned_start__lte=now, planned_end__gte=now, then=Value('Aktywne')),
            When(planned_start__gt=now, then=Value('Zaplanowane')),
            default=Value('Zakończone'),
            output_field=CharField(),
        )
    )
    if filter_kwargs:
        votings = votings.filter(**filter_kwargs)
    paginator = Paginator(votings, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/samorzad/partials/voting_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def list_candidates(request:HttpRequest):
    form = ListCandidatesForm()
    return render(request, 'panel/samorzad/candidates_list.html', context={
        'form':form
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_list_candidates(request:HttpRequest):
    SORT_MAP = {
        'name': ['first_name', 'second_name', 'last_name'],
        'creation': ['created_at'],
        'update': ['updated_at'],
        'id':['id'],
    }
    form = ListCandidatesForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    candidate_search = form.cleaned_data.get('candidate_search')
    class_search = form.cleaned_data.get('class_search')
    if candidate_search is None or candidate_search == '':
        candidates = Candidate.objects.all().order_by(*sort_data['sort_fields'])
    else:
        vector = SearchVector('first_name', 'second_name', 'last_name')
        search = SearchQuery(candidate_search, search_type='plain')
        candidates = Candidate.objects.annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_data['sort_fields'])
    if class_search != '':
        candidates = candidates.filter(school_class=class_search.upper())
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(candidates, 20)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/samorzad/partials/candidates_list.html', context={
        'page_obj': page_obj,
        'querystring':querystring,
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def list_candidatures(request:HttpRequest):
    form = ListCandidaturesForm()
    return render(request, 'panel/samorzad/candidatures_list.html', context={
        'form':form
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_list_candidatures(request:HttpRequest):
    SORT_MAP = {
        'name': ['candidate__first_name', 'candidate__second_name', 'candidate__last_name'],
        'creation': ['created_at'],
        'update': ['updated_at'],
        'id':['id'],
        'voting_id':['voting__id']
    }
    FILTER_MAP = {
        'is_eligible': {
            'field': 'is_eligible',
        },
    }
    form = ListCandidaturesForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    filter_data = build_filter_kwargs(FILTER_MAP, form.cleaned_data)
    candidate_search = form.cleaned_data.get('candidate_search')
    if candidate_search is None:
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').order_by(*sort_data['sort_fields'])
    else:
        vector = SearchVector('candidate__first_name', 'candidate__second_name', 'candidate__last_name')
        search = SearchQuery(candidate_search, search_type='plain')
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_data['sort_fields'])
    if filter_data:
        candidatures = candidatures.filter(**filter_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    paginator = Paginator(candidatures, 20)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/samorzad/partials/candidatures_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })

# UPDATE views

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_voting(request:HttpRequest, voting_id:int):
    """Widok edycji głosowania. Oparty na widoku tworzenia"""
    voting = get_object_or_404(Voting, pk=voting_id)
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Pola z datami muszą wskazywać na przyszłe daty',
            'Wartość głosów do oddania musi być większa niż 0'
        ]
        form = SamorzadAddEmptyVotingForm(instance=voting)
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = SamorzadAddEmptyVotingForm(request.POST, instance=voting)
        if form.is_valid():
            changed_data = get_changed_fields(form)
            try:
                form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:update_voting', kwargs={'voting_id':voting_id}))
            except Exception as Ex:
                messages.error(request, message="Nie udało się edytować głosowania", extra_tags='danger')
                return redirect(reverse('panel:update_voting', kwargs={'voting_id':voting_id}))
            messages.success(request, f'Zaktualizowano dane głosowania o ID: {voting_id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_index'),
                'add_new':reverse('panel:samorzad_add_empty_voting'),
                'edit':reverse('panel:update_voting', kwargs={'voting_id':voting_id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            return redirect(reverse('panel:update_voting', kwargs={'voting_id':voting_id}))


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_candidate(request:HttpRequest, candidate_id:int):
    """Widok edycji kandydata oparty na widoku tworzenia"""
    candidate = get_object_or_404(Candidate, pk=candidate_id)
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Klasa musi mieć wartość w formacie: "numer nazwa" np: 4 TI',
        ]
        form = SamorzadAddCandidateForm(instance=candidate)
        return render(request, 'panel/samorzad/samorzad_add_candidate.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = SamorzadAddCandidateForm(request.POST, request.FILES, instance=candidate)
        if form.is_valid():
            changed_data = get_changed_fields(form)
            try:
                candidate = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id}))
            except Exception as Ex:
                messages.error(request, message=f"Nie udało się edytować kandydata nr {candidate_id}", extra_tags='danger')
                return redirect(reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id}))
            messages.success(request, f'Zaktualizowano dane kandydata o ID: {candidate_id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidates'),
                'add_new':reverse('panel:samorzad_add_candidate'),
                'edit':reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, message=error, extra_tags='danger')
            return redirect(reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id}))




@require_http_methods(["GET", 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_candidature(request:HttpRequest, candidature_id:int):
    REQUIREMENTS_TIPS = [
        'Kandydat może mieć tylko jedną kandydaturę w ramach 1 głosowania',
        "Można wybrac tylko przyszłe głosowania"
    ]
    candidature = get_object_or_404(CandidateRegistration, pk=candidature_id)
    electoral_program = ElectoralProgram.objects.filter(candidature=candidature).first()
    if request.method == 'GET':
        candidature_form = CandidateRegistrationForm(instance=candidature)
        electoral_form = ElectoralProgramForm(instance=electoral_program)
        votings = Voting.objects.filter(planned_start__gt=timezone.now()).order_by('planned_start')
        selected_candidate = candidature_form.instance.candidate
        return render(request, 'panel/samorzad/samorzad_add_candidature.html', context={
            'votings':votings,
            'candidature_form':candidature_form,
            'electoral_form':electoral_form,
            'selected_candidate':selected_candidate,
            'candidate_id':candidature.candidate.id,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        candidature_form = CandidateRegistrationForm(request.POST, instance=candidature)
        electoral_form = ElectoralProgramForm(request.POST, instance=electoral_program)
        if candidature_form.is_valid() and electoral_form.is_valid():
            candidature_update_data = get_changed_fields(candidature_form)
            program_update_data = get_changed_fields(electoral_form)
            with transaction.atomic():
                candidature = candidature_form.save()
                program = electoral_form.save(commit=False)
                program.candidature = candidature
                program.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.UPDATE,
                    altered_fields=candidature_update_data,
                    content_type=ContentType.objects.get_for_model(CandidateRegistration),
                    object_id=candidature_id,
                )
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.UPDATE,
                    altered_fields=program_update_data,
                    content_type=ContentType.objects.get_for_model(ElectoralProgram),
                    object_id=program.id,
                )
            messages.success(request, f'Zaktualizowano dane kandydatury o ID: {candidature_id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_list_candidatures'),
                'add_new':reverse('panel:samorzad_add_candidature'),
                'edit':reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in candidature_form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            for field, errors in electoral_form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id}))


# DELETE views

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_voting(request:HttpRequest):
    """Widok usuwania głosowania. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    voting_id = request.POST.get('voting_id')
    if not voting_id or not voting_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID głosowania", redirect_url=reverse('panel:samorzad_index'))
    voting = Voting.objects.filter(id=voting_id).first()
    if voting:
        try:
            voting.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message=f"Pomyślnie usunięto głosowanie o id {voting_id}",
                                                  redirect_url=reverse('panel:samorzad_index'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR, message=Ex.message,
                                                  redirect_url=reverse('panel:update_voting', kwargs={'voting_id':voting_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR, message="Wystąpił błąd podczas próby głosowania",
                                                  redirect_url=reverse('panel:update_voting', kwargs={'voting_id':voting_id}))
    else:
        return build_delete_feedback_response(request, type=ERROR, message="Wystąpił błąd podczas próby usunięcia głosowania",
                                              redirect_url=reverse('panel:update_voting',
                                                                   kwargs={'voting_id': voting_id}))

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidate(request:HttpRequest):
    """Widok usuwania kandydata. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    candidate_id = request.POST.get('candidate_id')
    if not candidate_id or not candidate_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID kandydata", redirect_url=reverse('panel:list_candidates'))
    candidate = Candidate.objects.filter(id=candidate_id).first()
    if candidate:
        try:
            candidate.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message=f"Pomyślnie usunięto kandydata o id {candidate_id}",
                                                  redirect_url=reverse('panel:list_candidates'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR, message=Ex.message,
                                                  redirect_url=reverse('panel:update_candidate',
                                                                       kwargs={'candidate_id': candidate_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR, message=f"Wystąpił błąd podczas usuwania kandydata {candidate_id}",
                                                  redirect_url=reverse('panel:update_candidate',
                                                                       kwargs={'candidate_id': candidate_id}))

    else:
        return build_delete_feedback_response(request, type=ERROR, message="Wystąpił błąd podczas próby usunięcia kandydata",
                                              redirect_url=reverse('panel:update_candidate',
                                                                   kwargs={'candidate_id': candidate_id}))

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidature(request:HttpRequest):
    """Widok usuwania kandydata. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    candidature_id = request.POST.get('candidature_id')
    if not candidature_id or not candidature_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID kandydatury",
                                              redirect_url=reverse('panel:samorzad_list_candidatures'))
    candidature = CandidateRegistration.objects.filter(id=candidature_id).first()
    if candidature:
        try:
            candidature.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message=f"Pomyślnie usunięto kandydaturę o id {candidature_id}",
                                                  redirect_url=reverse('panel:samorzad_list_candidatures'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR, message=Ex.message,
                                                  redirect_url=reverse('panel:update_registration',
                                                                       kwargs={'candidature_id': candidature_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message=f"Wystąpił błąd podczas usuwania kandydatury {candidature_id}",
                                                  redirect_url=reverse('panel:update_registration',
                                                                       kwargs={'candidature_id': candidature_id}))
        return HttpResponse('', status=200)
    else:
        return build_delete_feedback_response(request, type=ERROR,
                                              message="Wystąpił błąd podczas próby usunięcia kandydatury",
                                              redirect_url=reverse('panel:update_registration',
                                                                   kwargs={'candidature_id': candidature_id}))

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def redirect_to_candidature(request:HttpRequest, electoral_program_id:int):
    candidature = get_object_or_404(CandidateRegistration, electoral_program=electoral_program_id)
    return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id}))


