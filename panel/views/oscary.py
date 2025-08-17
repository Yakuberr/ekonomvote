from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
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
from django.db.models import Case, When, Value, CharField, OuterRef, Subquery, DateTimeField, IntegerField
from django.template.loader import render_to_string
from django.contrib.messages.constants import ERROR, SUCCESS, WARNING, INFO

import pytz
from urllib.parse import urlencode

from oscary.models import VotingEvent,VotingRound, Vote, Candidature, Oscar, Teacher
from panel.forms import OscaryAddWholeVotingEventForm, SamorzadAddCandidateForm, CandidateRegistrationForm, ElectoralProgramForm, OscaryListVotingsForm
from office_auth.auth_utils import opiekun_required
from office_auth.models import ActionLog
from .utils import get_changed_fields, build_sort_list, build_filter_kwargs, build_delete_feedback_response
from .helpers import create_event_voting_db_helper, update_event_voting_db_helper

def _create_voting_status(voting:VotingRound):
    if voting.planned_start <= timezone.now() and voting.planned_end >= timezone.now():
        return 'Aktywne'
    elif voting.planned_end > timezone.now():
        return 'Zaplanowane'
    else:return 'Zakończone'


# CREATE views
# TODO: Walidcja czy id danego obiektu w bazie danych istnieje

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def create_voting_event(request:HttpRequest):
    """Widok do tworzenia za jednym zamachem wydarzenia głosowania oraz nominacji i głosowania finałowego"""
    REQUIREMENTS_TIPS = [
        'Zawiera nominacje: Ustawia czy wydarzenie zawiera nominacje. Uwaga pola nie można edytować',
        'Pola z datami muszą wskazywać na przyszłe daty',
        "Jeśli wydarzenie zawiera nominację to musi ona skończyć się przed rozpoczęciem rundy finałowej",
        "Liczba zwycięzców: Liczba nauczycieli którzy przechodzą do rundy finałowej dla danego oscara. W finale wygrywa tylko 1 nauczyciel na oscara"
    ]
    if request.method == 'GET':
        form = OscaryAddWholeVotingEventForm()
        return render(request, 'panel/oscary/add_voting.html', context={
            'form': form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryAddWholeVotingEventForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            try:
                voting_event = create_event_voting_db_helper(cleaned_data, request=request)
            except ValidationError:
                messages.add_message(request, level=40, message="Nie udało się dodać głosowań")
                return redirect(reverse('panel:create_voting_event'))
            messages.success(request, f'Dodano wydarzenie o ID: {voting_event.id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list': reverse('panel:list_voting_events'),
                'add_new': reverse('panel:create_voting_event'),
                'edit': reverse('panel:update_voting_event', kwargs={'voting_event_id': voting_event.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:create_voting_event'))


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_voting_event(request:HttpRequest, voting_event_id:int):
    """Widok do edycji za jednym zamachem wydarzenia głosowania oraz nominacji i głosowania finałowego"""
    REQUIREMENTS_TIPS = [
        'Zawiera nominacje: Ustawia czy wydarzenie zawiera nominacje. Uwaga pola nie można edytować',
        'Pola z datami muszą wskazywać na przyszłe daty',
        "Jeśli wydarzenie zawiera nominację to musi ona skończyć się przed rozpoczęciem rundy finałowej",
        "Liczba zwycięzców: Liczba nauczycieli którzy przechodzą do rundy finałowej dla danego oscara. W finale wygrywa tylko 1 nauczyciel na oscara"
    ]
    voting_event = get_object_or_404(VotingEvent, pk=voting_event_id)
    voting_final = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.FINAL, voting_event=voting_event).first()
    if request.method == 'GET':
        initial = {
            'with_nominations': voting_event.with_nominations,
            'l_round_start': voting_final.localize_dt(voting_final.planned_start).strftime('%Y-%m-%d %H:%M'),
            'l_round_end': voting_final.localize_dt(voting_final.planned_end).strftime('%Y-%m-%d %H:%M'),
        }
        if voting_event.with_nominations:
            voting_nomination = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.NOMINATION,
                                                           voting_event=voting_event).first()
            initial.update({
                'f_round_start': voting_nomination.localize_dt(voting_nomination.planned_start).strftime('%Y-%m-%d %H:%M'),
                'f_round_end': voting_nomination.localize_dt(voting_nomination.planned_end).strftime('%Y-%m-%d %H:%M'),
                'f_round_t_count': voting_nomination.max_tearchers_for_end,
            })
        form = OscaryAddWholeVotingEventForm(initial=initial)
        return render(request, 'panel/oscary/add_voting.html', context={
            'form':form,
            'voting_event_id':voting_event.id,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryAddWholeVotingEventForm(request.POST)
        if form.is_valid():
            try:
                voting_nomination_id = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.NOMINATION, voting_event=voting_event).first().id
            except AttributeError:
                voting_nomination_id = None
            voting_final_id = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.FINAL,
                                                              voting_event=voting_event).first().id
            try:
                with transaction.atomic():
                    update_event_voting_db_helper(form.cleaned_data, voting_event_id, voting_nomination_id, voting_final_id, with_nominations=voting_event.with_nominations)
            except Exception as Ex:
                messages.error(request, message=f'Wystąpił problem z aktualizacją')
                return redirect(reverse('panel:update_voting_event', kwargs={'voting_event_id':voting_event_id}))
            messages.success(request, f'Zaktualizowano dane głosowania o ID: {voting_event_id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_voting_events'),
                'add_new':reverse('panel:create_voting_event'),
                'edit':reverse('panel:update_voting_event', kwargs={'voting_event_id':voting_event_id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:update_voting', kwargs={'voting_id':voting_event_id}))


@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_voting_event(request:HttpRequest):
    """Widok usuwania wydarzenia głosowania. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    voting_event_id = request.POST.get('voting_event_id')
    htmx = request.headers.get('HX-Request')
    if not voting_event_id or not voting_event_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID wydarzenia", redirect_url=reverse('panel:list_voting_events'))
    voting_event = VotingEvent.objects.filter(id=voting_event_id).first()
    if voting_event:
        try:
            voting_event.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message='Pomyślnie usunięto wydarzenie', redirect_url=reverse('panel:list_voting_events'), alert_template=None)
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message='Wystąpił błąd podczas próby usunięcia głosowania',
                                                  redirect_url=reverse('panel:update_voting_event',
                                                                       kwargs={'voting_event_id': voting_event_id}))
    else:
        return build_delete_feedback_response(request, type=ERROR, message='Wystąpił błąd podczas próby usunięcia głosowania', redirect_url=reverse('panel:update_voting_event', kwargs={'voting_event_id':voting_event_id}))


@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def list_voting_events(request:HttpRequest):
    form = OscaryListVotingsForm()
    status_list = ['Zakończone', "Aktywne", 'Zaplanowane']
    nominations_choices = form.fields['nominations'].choices
    return render(request, 'panel/oscary/votings_list.html', context={
        'status_list': status_list,
        'nominations_choices':nominations_choices,
        'form':form
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_list_voting_events(request:HttpRequest):
    SORT_MAP = {
        'nomination_start':['first_round_start'],
        'final_start': ['last_round_start'],
        'creation':['created_at'],
        'update':['updated_at'],
        'id':['id']
    }
    FILTER_MAP = {
        'nominations': {
            'field': 'with_nominations',
        },
    }
    form = OscaryListVotingsForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    print(sort_data)
    filter_data = build_filter_kwargs(FILTER_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    voting_events = VotingEvent.objects.prefetch_related('voting_rounds')
    first_round_start = VotingRound.objects.filter(
        voting_event=OuterRef('pk')
    ).order_by('planned_start').values('planned_start')[:1]
    first_round_end = VotingRound.objects.filter(
        voting_event=OuterRef('pk')
    ).order_by('planned_end').values('planned_end')[:1]
    last_round_start = VotingRound.objects.filter(
        voting_event=OuterRef('pk')
    ).order_by('-planned_start').values('planned_start')[:1]
    last_round_end = VotingRound.objects.filter(
        voting_event=OuterRef('pk')
    ).order_by('-planned_end').values('planned_end')[:1]
    teachers_per_end = VotingRound.objects.filter(voting_event=OuterRef('pk')).order_by('planned_start').values('max_tearchers_for_end')[:1]
    voting_events = VotingEvent.objects.annotate(
        first_round_start=Case(
            When(with_nominations=True, then=Subquery(first_round_start, output_field=DateTimeField())),
            default=Value(None),
            output_field=DateTimeField(),
        ),
        first_round_end=Case(
            When(with_nominations=True, then=Subquery(first_round_end, output_field=DateTimeField())),
            default=Value(None),
            output_field=DateTimeField(),
        ),
        last_round_start=Subquery(last_round_start, output_field=DateTimeField(), ),
        last_round_end=Subquery(last_round_end, output_field=DateTimeField(), ),
    ).annotate(teachers_per_end=Subquery(teachers_per_end, output_field=IntegerField(), ))
    voting_events = voting_events.order_by(*sort_data['sort_fields'])
    if len(filter_data) != 0:
        voting_events = voting_events.filter(**filter_data)
    events = list(voting_events)
    if statuses := form.cleaned_data.get('event_status'):
        events = [e for e in events if e.get_event_status(now) in statuses]
    paginator = Paginator(events, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    if form.cleaned_data.get('event_status') is not None:
        paginator.object_list = filter(lambda item:item.get_event_status in form.cleaned_data.get('event_status'),  paginator.object_list)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/oscary/partials/voting_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })



@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def create_teacher(request:HttpRequest):
    if request.method == 'GET':
        form = SamorzadAddCandidateForm()
        return render(request, 'panel/samorzad/samorzad_add_candidate.html', context={
            'form':form
        })
    if request.method == 'POST':
        form = SamorzadAddCandidateForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                candidate = form.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.CREATE,
                    altered_fields={},
                    content_type=ContentType.objects.get_for_model(Candidate),
                    object_id=candidate.id,
                )
            messages.success(request, f'Dodano pomyślnie nowego kandydata {candidate.first_name} {candidate.second_name} {candidate.last_name}, ID: {candidate.id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidates'),
                'add_new':reverse('panel:samorzad_add_candidate'),
                'edit':reverse('panel:update_candidate', kwargs={'candidate_id':candidate.id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:samorzad_add_candidate'))

@require_http_methods(["GET", 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def create_candidature(request:HttpRequest):
    if request.method == 'GET':
        candidature_form = CandidateRegistrationForm()
        electoral_form = ElectoralProgramForm()
        votings = Voting.objects.filter(planned_start__gt=timezone.now()).order_by('planned_start')
        return render(request, 'panel/samorzad/samorzad_add_candidature.html', context={
            'votings':votings,
            'candidature_form':candidature_form,
            'electoral_form':electoral_form,
            'candidate_id':None,
        })
    if request.method == 'POST':
        candidature_form = CandidateRegistrationForm(request.POST)
        electoral_form = ElectoralProgramForm(request.POST)
        if candidature_form.is_valid() and electoral_form.is_valid():
            with transaction.atomic():
                candidature = candidature_form.save()
                program = electoral_form.save(commit=False)
                program.candidature = candidature
                program.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.CREATE,
                    altered_fields={},
                    content_type=ContentType.objects.get_for_model(CandidateRegistration),
                    object_id=candidature.id,
                )
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.CREATE,
                    altered_fields={},
                    content_type=ContentType.objects.get_for_model(ElectoralProgram),
                    object_id=program.id,
                )
            messages.success(request, f'Dodano pomyślnie nową kandydaturę od ID: {candidature.id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidatures'),
                'add_new':reverse('panel:samorzad_add_candidature'),
                'edit':reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in candidature_form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            for field, errors in electoral_form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:samorzad_add_candidature'))


@require_http_methods(["GET"])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_candidates_search(request:HttpRequest):
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
def read_voting_event_list(request:HttpRequest):
    status_list = ['Aktywne', 'Zaplanowane', 'Zakończone']
    return render(request, 'panel/samorzad/samorzad_index.html', context={
        'status_list': status_list,
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_read_voting_list_event(request:HttpRequest):
    SORT_MAP = {
        'planned_start':['planned_start'],
        'planned_end':['planned_end'],
        'created_at':['created_at'],
        'updated_at':['updated_at'],
        'id':['id']
    }
    FILTER_MAP = {
        'f_status': {
            'field': 'status__in',
            'allowed_values': ['Zaplanowane', "Aktywne", "Zakończone"],
        },
    }
    sort_data = build_sort_list(SORT_MAP, request.GET)
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
    filter_kwargs = build_filter_kwargs(FILTER_MAP, request.GET)
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
def read_teacher_list(request:HttpRequest):
    return render(request, 'panel/samorzad/candidates_list.html', context={
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_list_teachers(request:HttpRequest):
    SORT_MAP = {
        'name': ['first_name', 'second_name', 'last_name'],
        'created_at': ['created_at'],
        'updated_at': ['updated_at'],
        'id':['id'],
    }
    sort_data = build_sort_list(SORT_MAP, request.GET)
    query = request.GET.get('search')
    if query is None or query == '':
        candidates = Candidate.objects.all().order_by(*sort_data['sort_fields'])
        query = ''
    else:
        vector = SearchVector('first_name', 'second_name', 'last_name')
        search = SearchQuery(query, search_type='plain')
        candidates = Candidate.objects.annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_data['sort_fields'])
    class_query = request.GET.get('search_class', '')
    if class_query != '':
        candidates = candidates.filter(school_class=class_query.upper())
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
    return render(request, 'panel/samorzad/candidatures_list.html', context={})

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_list_candidatures(request:HttpRequest):
    query = request.GET.get('search')
    SORT_MAP = {
        'name': ['candidate__first_name', 'candidate__second_name', 'candidate__last_name'],
        'planned_start': ['voting__planned_start'],
        'created_at': ['created_at'],
        'updated_at': ['updated_at'],
        'id':['id']
    }
    FILTER_MAP = {
        'f_eligible': {
            'field': 'is_eligible',
            'allowed_values': ['0', '1'],
        },
    }
    filter_data = None
    if request.GET.get('f_eligible') is not None:
        if request.GET.get('f_eligible') in FILTER_MAP['f_eligible']['allowed_values']:
            filter_data = {}
            filter_data[FILTER_MAP['f_eligible']['field']] = bool(int(request.GET.get('f_eligible')))
    sort_data = build_sort_list(SORT_MAP, request.GET)
    if query is None or query == '':
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').order_by(*sort_data['sort_fields'])
        query = ''
    else:
        vector = SearchVector('candidate__first_name', 'candidate__second_name', 'candidate__last_name')
        search = SearchQuery(query, search_type='plain')
        candidatures = CandidateRegistration.objects.select_related('candidate', 'voting').annotate(rank=SearchRank(vector, search)).filter(rank__gte=0.03).order_by('-rank', *sort_data['sort_fields'])
    if filter_data is not None:
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
    voting = get_object_or_404(Voting, pk=voting_id)
    if request.method == 'GET':
        form = SamorzadAddEmptyVotingForm(instance=voting)
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form':form
        })
    if request.method == 'POST':
        form = SamorzadAddEmptyVotingForm(request.POST, instance=voting)
        if form.is_valid():
            changed_data = get_changed_fields(form)
            with transaction.atomic():
                form.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.UPDATE,
                    altered_fields=changed_data,
                    content_type=ContentType.objects.get_for_model(Voting),
                    object_id=voting_id,
                )
            messages.success(request, f'Zaktualizowano dane głosowania o ID: {voting_id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_index'),
                'add_new':reverse('panel:samorzad_add_empty_voting'),
                'edit':reverse('panel:update_voting', kwargs={'voting_id':voting_id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:update_voting', kwargs={'voting_id':voting_id}))
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form':form
        })


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_candidate(request:HttpRequest, candidate_id:int):
    candidate = get_object_or_404(Candidate, pk=candidate_id)
    if request.method == 'GET':
        form = SamorzadAddCandidateForm(instance=candidate)
        return render(request, 'panel/samorzad/samorzad_add_candidate.html', context={
            'form':form
        })
    if request.method == 'POST':
        form = SamorzadAddCandidateForm(request.POST, request.FILES, instance=candidate)
        if form.is_valid():
            changed_data = get_changed_fields(form)
            with transaction.atomic():
                form.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.UPDATE,
                    altered_fields=changed_data,
                    content_type=ContentType.objects.get_for_model(Candidate),
                    object_id=candidate_id,
                )
            messages.success(request, f'Zaktualizowano dane kandydata o ID: {candidate_id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidates'),
                'add_new':reverse('panel:samorzad_add_candidate'),
                'edit':reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:update_candidate', kwargs={'candidate_id':candidate_id}))




@require_http_methods(["GET", 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_candidature(request:HttpRequest, candidature_id:int):
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
            'candidate_id':candidature.candidate.id
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
                'list':reverse('panel:list_candidatures'),
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
def delete_candidate(request:HttpRequest):
    candidate_id = request.POST.get('candidate_id')
    if not candidate_id or not candidate_id.isdigit():
        return render(request, 'alert.html',context={
            'type': 'danger',
            'message': 'Nieprawidłowe ID kandydata.'
        })
    candidate = Candidate.objects.filter(id=candidate_id).first()
    if candidate:
        with transaction.atomic():
            candidate.delete()
            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                altered_fields={},
                content_type=ContentType.objects.get_for_model(Candidate),
                object_id=candidate_id,
            )
        return HttpResponse(content='', status=200)
    else:
        return render(request, 'alert.html', context={
            'type': 'danger',
            'message': 'Wystąpił błąd podczas próby usunięcia kandydata.'
        })

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidature(request:HttpRequest):
    candidature_id = request.POST.get('candidature_id')
    if not candidature_id or not candidature_id.isdigit():
        return render(request, 'alert.html',context={
            'type': 'danger',
            'message': 'Nieprawidłowe ID kandydatury.'
        })
    candidature = CandidateRegistration.objects.filter(id=candidature_id).first()
    if candidature:
        try:
            program_id = candidature.electoral_program.id
        except ObjectDoesNotExist:
            program_id = None
        with transaction.atomic():
            candidature.delete()
            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                altered_fields={},
                content_type=ContentType.objects.get_for_model(CandidateRegistration),
                object_id=candidature_id,
            )
            if program_id is not None:
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.DELETE,
                    altered_fields={},
                    content_type=ContentType.objects.get_for_model(ElectoralProgram),
                    object_id=program_id,
                )
        return HttpResponse('', status=200)
    else:
        return render(request, 'alert.html',context={
            'type': 'danger',
            'message': 'Wystąpił błąd podczas próby usunięcia kandydatury.'
        })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def redirect_to_candidature(request:HttpRequest, electoral_program_id:int):
    candidature = get_object_or_404(CandidateRegistration, electoral_program=electoral_program_id)
    return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id}))


