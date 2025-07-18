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
from django.db.models import Case, When, Value, CharField

import pytz
from urllib.parse import urlencode

from samorzad.models import Voting, Candidate, CandidateRegistration, ElectoralProgram
from panel.forms import SamorzadAddEmptyVotingForm, SamorzadAddCandidateForm, CandidateRegistrationForm, ElectoralProgramForm
from office_auth.auth_utils import opiekun_required
from office_auth.models import ActionLog
from .utils import get_changed_fields, build_sort_list, build_filter_kwargs

def _create_voting_status(voting:Voting):
    if voting.planned_start <= timezone.now() and voting.planned_end >= timezone.now():
        return 'Aktywne'
    elif voting.planned_end > timezone.now():
        return 'Zaplanowane'
    else:return 'Zakończone'


# CREATE views
# TODO: Walidcja czy id danego obiektu w bazie danych istnieje

# TODO: Pełna walidacja powiązń pomiędzy CandidatureRegistration i ElectoralProgram

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def add_empty_voting(request:HttpRequest):
    if request.method == 'GET':
        form = SamorzadAddEmptyVotingForm()
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form': form
        })
    if request.method == 'POST':
        form = SamorzadAddEmptyVotingForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                voting = form.save()
                ActionLog.objects.create(
                    user=request.user,
                    action_type=ActionLog.ActionType.CREATE,
                    altered_fields={},
                    content_type=ContentType.objects.get_for_model(Voting),
                    object_id=voting.id,
                )
            messages.success(request, f'Dodano pomyślnie nowe głosowanie o ID: {voting.id}')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:samorzad_index'),
                'add_new':reverse('panel:samorzad_add_empty_voting'),
                'edit':reverse('panel:update_voting', kwargs={'voting_id':voting.id})
            }
            return redirect(URL_MAP[redirect_to])
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error)
            return redirect(reverse('panel:samorzad_add_empty_voting'))
        return render(request, 'panel/samorzad/samorzad_add_empty_voting.html', context={
            'form':form
        })

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def samorzad_add_candidate(request:HttpRequest):
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
def samorzad_add_candidature(request:HttpRequest):
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
def samorzad_index(request:HttpRequest):
    status_list = ['Aktywne', 'Zaplanowane', 'Zakończone']
    return render(request, 'panel/samorzad/samorzad_index.html', context={
        'status_list': status_list,
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_read_voting_list(request:HttpRequest):
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
def list_candidates(request:HttpRequest):
    return render(request, 'panel/samorzad/candidates_list.html', context={
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
@opiekun_required()
def partial_list_candidates(request:HttpRequest):
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
        candidates = candidates.filter(school_class=class_query)
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
def delete_voting(request:HttpRequest):
    voting_id = request.POST.get('voting_id')
    if not voting_id or not voting_id.isdigit():
        messages.error(request, 'Nieprawidłowe ID głosowania.')
        return redirect(reverse('panel:samorzad_index'))
    voting = Voting.objects.filter(id=voting_id).first()
    if voting:
        with transaction.atomic():
            voting.delete()
            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.DELETE,
                altered_fields={},
                content_type=ContentType.objects.get_for_model(Voting),
                object_id=voting_id,
            )
        messages.success(
            request,
            f'Pomyślnie usunięto głosowanie: ID: {voting_id}'
        )
    else:
        messages.error(request, 'Głosowanie o podanym ID nie istnieje.')
    params = {
        'sort':request.POST.get('sort'),
        'order':request.POST.get('order'),
        'page':request.POST.get('page'),
    }
    filtered_params = {k: v for k, v in params.items() if v}
    url = reverse('panel:samorzad_index') + '?' + urlencode(filtered_params)
    return redirect(url)

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidate(request:HttpRequest):
    candidate_id = request.POST.get('candidate_id')
    if not candidate_id or not candidate_id.isdigit():
        messages.error(request, 'Nieprawidłowe ID kandydata.')
        return redirect(reverse('panel:list_candidates'))
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
        messages.success(
            request,
            f'Pomyślnie usunięto kandydata: {candidate.first_name} {candidate.second_name} {candidate.last_name}, ID: {candidate_id}'
        )
    else:
        messages.error(request, 'Kandydat o podanym ID nie istnieje.')
    params = {
        'sort':request.POST.get('sort'),
        'search':request.POST.get('search'),
        'order':request.POST.get('order'),
        'page':request.POST.get('page'),
    }
    filtered_params = {k: v for k, v in params.items() if v}
    url = reverse('panel:list_candidates') + '?' + urlencode(filtered_params)
    return redirect(url)

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidature(request:HttpRequest):
    candidature_id = request.POST.get('candidature_id')
    if not candidature_id or not candidature_id.isdigit():
        messages.error(request, 'Nieprawidłowe ID kandydatury.')
        return redirect(reverse('panel:list_candidatures'))
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
        messages.success(
            request,
            f'Pomyślnie usunięto kandydaturę o ID: {candidature_id}'
        )
    else:
        messages.error(request, 'Kandydatura o podanym ID nie istnieje.')
    params = {
        'sort':request.POST.get('sort'),
        'search':request.POST.get('search'),
        'order':request.POST.get('order'),
        'page':request.POST.get('page'),
    }
    filtered_params = {k: v for k, v in params.items() if v}
    url = reverse('panel:list_candidates') + '?' + urlencode(filtered_params)
    return redirect(url)

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def redirect_to_candidature(request:HttpRequest, electoral_program_id:int):
    candidature = get_object_or_404(CandidateRegistration, electoral_program=electoral_program_id)
    return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id}))

# TODO: Timelinechart powinien wyświetlać dane DO momentu zakończenia głosowania




