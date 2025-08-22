from django.contrib.auth.views import LoginView
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpRequest, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import redirect, render, reverse, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from django.contrib.postgres.search import SearchRank, SearchQuery, SearchVector
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Case, When, Value, CharField, OuterRef, Subquery, DateTimeField, IntegerField, \
    BigIntegerField
from django.template.loader import render_to_string
from django.contrib.messages.constants import ERROR, SUCCESS, WARNING, INFO

import pytz
from urllib.parse import urlencode

from oscary.models import VotingEvent,VotingRound, Vote, Candidature, Oscar, Teacher
from panel.forms import (OscaryAddWholeVotingEventForm,
                         SamorzadAddCandidateForm,
                         CandidateRegistrationForm,
                         ElectoralProgramForm,
                         OscaryListVotingsForm,
                         OscaryCreateOscarForm,
                         OscaryListOscarsForm,
                         OscaryCreateTeacher,
                         OscaryListTeachersForm,
                         OscaryCreateCandidatureForm, OscaryListCandidaturesForm)
from office_auth.auth_utils import opiekun_required
from office_auth.models import ActionLog
from .utils import get_changed_fields, build_sort_list, build_filter_kwargs, build_delete_feedback_response
from .helpers import OscarHelpers

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
        "Liczba zwycięzców: Liczba nauczycieli którzy przechodzą do rundy finałowej dla danego oscara. W finale wygrywa tylko 1 nauczyciel na oscara",
        "UWAGA podczas tworzenia wydarzenia, kandydatury zostaną dodane automatycznie dodane do systemu. Może to zająć kilka sekund"
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
                voting_event = OscarHelpers.create_event_voting_db_helper(cleaned_data, request=request)
            except ValidationError:
                messages.add_message(request, level=40, message="Nie udało się dodać głosowań", extra_tags='danger')
                return redirect(reverse('panel:create_voting_event'))
            messages.success(request, f'Dodano wydarzenie o ID: {voting_event.id}', extra_tags='success')
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
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
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
                    OscarHelpers.update_event_voting_db_helper(form.cleaned_data, voting_event_id, voting_nomination_id, voting_final_id, with_nominations=voting_event.with_nominations)
            except Exception as Ex:
                messages.error(request, message=f'Wystąpił problem z aktualizacją', extra_tags='danger')
                return redirect(reverse('panel:update_voting_event', kwargs={'voting_event_id':voting_event_id}))
            messages.success(request, f'Zaktualizowano dane głosowania o ID: {voting_event_id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_voting_events'),
                'add_new':reverse('panel:create_voting_event'),
                'edit':reverse('panel:update_voting_event', kwargs={'voting_event_id':voting_event_id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
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
    filter_data = build_filter_kwargs(FILTER_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    voting_events = OscarHelpers.partial_list_voting_events_db_helper(
        sort_data=sort_data,
        filter_data=filter_data,
        page_number=page_number,
        now=now
    )
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
def create_oscar(request:HttpRequest):
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Nazwa oscara musi być unikalna',
        ]
        form = OscaryCreateOscarForm()
        return render(request, 'panel/oscary/add_oscar.html', context={
            'form': form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryCreateOscarForm(request.POST)
        if form.is_valid():
            try:
                oscar = form.save()
            except Exception as Ex:
                messages.add_message(request, 40, "Nie udało się dodać oscara", extra_tags='danger')
                return redirect(reverse('panel:create_oscar'))
            except ValidationError as Ex:
                messages.add_message(request, 40, Ex.message, extra_tags='danger')
                return redirect(reverse('panel:create_oscar'))
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list': reverse('panel:list_oscars'),
                'add_new': reverse('panel:create_oscar'),
                'edit': reverse('panel:update_oscar', kwargs={'oscar_id': oscar.id})
            }
            messages.success(request, message=f"Pomyślnie dodano oscara nr {oscar.id}", extra_tags='success')
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:create_oscar'))

@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_oscar(request:HttpRequest, oscar_id:int):
    oscar = get_object_or_404(Oscar, id=oscar_id)
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Nazwa oscara musi być unikalna',
        ]
        form = OscaryCreateOscarForm(instance=oscar)
        return render(request, 'panel/oscary/add_oscar.html', context={
            'form': form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryCreateOscarForm(request.POST, instance=oscar)
        if form.is_valid():
            try:
                form.save()
            except Exception as Ex:
                messages.add_message(request, 40, "Nie udało się dodać oscara", extra_tags='danger')
                redirect(reverse('panel:update_oscar', kwargs={'oscar_id':oscar.id}))
            except ValidationError as Ex:
                messages.add_message(request, 40, Ex.message, extra_tags='danger')
                redirect(reverse('panel:update_oscar', kwargs={'oscar_id':oscar.id}))
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list': reverse('panel:list_oscars'),
                'add_new': reverse('panel:create_oscar'),
                'edit': reverse('panel:update_oscar', kwargs={'oscar_id': oscar_id})
            }
            messages.success(request, message=f"Pomyślnie edytowano oscara nr {oscar_id}", extra_tags='success')
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:update_oscar', kwargs={'oscar_id':oscar.id}))


@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_oscar(request:HttpRequest):
    """Widok usuwania oscara. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    oscar_id = request.POST.get('oscar_id')
    htmx = request.headers.get('HX-Request')
    if not oscar_id or not oscar_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID oscara", redirect_url=reverse('panel:list_oscars'))
    oscar = Oscar.objects.filter(id=oscar_id).first()
    if oscar:
        try:
            oscar.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message='Pomyślnie usunięto oscara', redirect_url=reverse('panel:list_oscars'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message=Ex.message,
                                                  redirect_url=reverse('panel:update_oscar',
                                                                       kwargs={'oscar_id': oscar_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message='Wystąpił błąd podczas próby usunięcia oscara',
                                                  redirect_url=reverse('panel:update_oscar',
                                                                       kwargs={'oscar_id': oscar_id}))
    else:
        return build_delete_feedback_response(request, type=ERROR, message='Wystąpił błąd podczas próby usunięcia oscara', redirect_url=reverse('panel:update_oscar', kwargs={'oscar_id':oscar_id}))

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def list_oscars(request:HttpRequest):
    form = OscaryListOscarsForm()
    return render(request, 'panel/oscary/oscars_list.html', context={
        'form':form
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_list_oscars(request:HttpRequest):
    SORT_MAP = {
        'name':['name'],
        'creation':['created_at'],
        'update':['updated_at'],
        'id':['id']
    }
    form = OscaryListOscarsForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    if form.cleaned_data.get('search', '') != '':
        vector = SearchVector('name')
        query = SearchQuery(form.cleaned_data['search'], search_type='websearch')
        oscars = Oscar.objects.all().annotate(rank=SearchRank(vector=vector, query=query)).filter(rank__gt=0).order_by('-rank', *sort_data['sort_fields'])
    else:
        oscars = Oscar.objects.all().order_by(*sort_data['sort_fields'])
    paginator = Paginator(oscars, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/oscary/partials/oscars_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def create_teacher(request:HttpRequest):
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Zdjęcie musi mieć rozmiar 400x400 pixeli i ważyć nie więcej niż 2 MB',
        ]
        form = OscaryCreateTeacher()
        return render(request, 'panel/oscary/add_teacher.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryCreateTeacher(request.POST, request.FILES)
        if form.is_valid():
            try:
                teacher = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:create_teacher'))
            except Exception as Ex:
                messages.error(request, message="Nie udało się dodać nauczyciela", extra_tags='danger')
                return redirect(reverse('panel:create_teacher'))
            messages.success(request, f'Dodano pomyślnie nowego nauczyciela {teacher.first_name} {teacher.second_name} {teacher.last_name}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_teachers'),
                'add_new':reverse('panel:create_teacher'),
                'edit':reverse('panel:update_teacher', kwargs={'teacher_id':teacher.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:create_teacher'))


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_teacher(request:HttpRequest, teacher_id:int):
    teacher = get_object_or_404(Teacher, pk=teacher_id)
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Zdjęcie musi mieć rozmiar 400x400 pixeli i ważyć nie więcej niż 2 MB',
        ]
        form = OscaryCreateTeacher(instance=teacher)
        return render(request, 'panel/oscary/add_teacher.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS
        })
    if request.method == 'POST':
        form = OscaryCreateTeacher(request.POST, request.FILES, instance=teacher)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:update_teacher', kwargs={'teacher_id':teacher_id}))
            except Exception as Ex:
                messages.error(request, message="Nie udało się edytować nauczyciela", extra_tags='danger')
                return redirect(reverse('panel:update_teacher', kwargs={'teacher_id':teacher_id}))
            messages.success(request, f'Edytowano pomyślnie nowego nauczyciela {teacher.first_name} {teacher.second_name} {teacher.last_name}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_teachers'),
                'add_new':reverse('panel:create_teacher'),
                'edit':reverse('panel:update_teacher', kwargs={'teacher_id':teacher_id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:update_teacher', kwargs={'teacher_id':teacher_id}))


@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_teacher(request:HttpRequest):
    """Widok usuwania wydarzenia głosowania. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    teacher_id = request.POST.get('teacher_id')
    htmx = request.headers.get('HX-Request')
    if not teacher_id or not teacher_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID nauczyciela", redirect_url=reverse('panel:list_teachers'))
    teacher = Teacher.objects.filter(id=teacher_id).first()
    if teacher:
        try:
            teacher.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message='Pomyślnie usunięto nauczyciela', redirect_url=reverse('panel:list_teachers'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message=Ex,
                                                  redirect_url=reverse('panel:update_teacher',
                                                                       kwargs={'teacher_id': teacher_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message='Wystąpił błąd podczas próby usunięcia głosowania',
                                                  redirect_url=reverse('panel:update_teacher',
                                                                       kwargs={'teacher_id': teacher_id}))
    else:
        return build_delete_feedback_response(request, type=ERROR, message='Wystąpił błąd podczas próby usunięcia nauczyciela', redirect_url=reverse('panel:update_teacher', kwargs={'teacher_id':teacher_id}))


@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def list_teachers(request:HttpRequest):
    form = OscaryListTeachersForm()
    return render(request, 'panel/oscary/teachers_list.html', context={
        'form':form
    })


@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_list_teachers(request:HttpRequest):
    SORT_MAP = {
        'name':['first_name', 'second_name', 'last_name'],
        'creation':['created_at'],
        'update':['updated_at'],
        'id':['id']
    }
    form = OscaryListTeachersForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    if form.cleaned_data.get('search', '') != '':
        vector = SearchVector('first_name', 'second_name', 'last_name')
        query = SearchQuery(form.cleaned_data['search'], search_type='websearch')
        teachers = Teacher.objects.all().annotate(rank=SearchRank(vector=vector, query=query)).filter(rank__gt=0).order_by('-rank', *sort_data['sort_fields'])
    else:
        teachers = Teacher.objects.all().order_by(*sort_data['sort_fields'])
    paginator = Paginator(teachers, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/oscary/partials/teachers_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def create_candidature(request:HttpRequest):
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Nauczyciel nie może 2 razy kandydowac na oscara w jednej rundzie.',
        ]
        form = OscaryCreateCandidatureForm()
        oscars = Oscar.objects.all().order_by('name')
        first_round_pk = Subquery(VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_start').values('pk')[:1],
        output_field=BigIntegerField())
        first_round_start = Subquery(VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_start').values('planned_start')[:1],
        output_field=DateTimeField())
        events = VotingEvent.objects.prefetch_related('voting_rounds').annotate(first_round_start=first_round_start, first_round_pk=first_round_pk).filter(first_round_start__gt=timezone.now())
        teachers = Teacher.objects.all().order_by('first_name', 'second_name', 'last_name')
        return render(request, 'panel/oscary/add_candidature.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS,
            'oscars':oscars,
            'events':events,
            'teachers':teachers
        })
    if request.method == 'POST':
        form = OscaryCreateCandidatureForm(request.POST)
        if form.is_valid():
            try:
                candidature = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:create_candidature'))
            except Exception as Ex:
                messages.error(request, message="Nie udało się dodać kandydatury", extra_tags='danger')
                return redirect(reverse('panel:create_candidature'))
            messages.success(request, f'Dodano pomyślnie kandydaturę, id: {candidature.id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidatures'),
                'add_new':reverse('panel:create_candidature'),
                'edit':reverse('panel:update_candidature', kwargs={'candidature_id':candidature.id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:create_candidature'))


@require_http_methods(['GET', 'POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def update_candidature(request:HttpRequest, candidature_id:int):
    candidature = get_object_or_404(Candidature.objects.select_related('teacher', 'oscar', 'voting_round'), id=candidature_id)
    if request.method == 'GET':
        REQUIREMENTS_TIPS = [
            'Nauczyciel nie może 2 razy kandydowac na oscara w jednej rundzie.',
        ]
        form = OscaryCreateCandidatureForm(instance=candidature)
        oscars = Oscar.objects.all().order_by('name').exclude(id=candidature.oscar.id)
        first_round_pk = Subquery(VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_start').values('pk')[:1],
        output_field=BigIntegerField())
        first_round_start = Subquery(VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_start').values('planned_start')[:1],
        output_field=DateTimeField())
        events = VotingEvent.objects.prefetch_related('voting_rounds').annotate(first_round_start=first_round_start, first_round_pk=first_round_pk).filter(first_round_start__gt=timezone.now())
        teachers = Teacher.objects.all().order_by('first_name', 'second_name', 'last_name').exclude(id=candidature.teacher.id)
        selected_event = candidature.voting_round.voting_event
        events = events.exclude(id=selected_event.id)
        return render(request, 'panel/oscary/add_candidature.html', context={
            'form':form,
            'tips':REQUIREMENTS_TIPS,
            'oscars':oscars,
            'events':events,
            'teachers':teachers,
            'selected_event':selected_event
        })
    if request.method == 'POST':
        form = OscaryCreateCandidatureForm(request.POST, instance=candidature)
        if form.is_valid():
            try:
                candidature = form.save()
            except ValidationError as Ex:
                messages.error(request, message=Ex.message, extra_tags='danger')
                return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id}))
            except Exception as Ex:
                messages.error(request, message="Nie udało się edytować kandydatury", extra_tags='danger')
                return redirect(reverse('panel:create_candidature'))
            messages.success(request, f'Edytowano kandydaturę, id: {candidature.id}', extra_tags='success')
            redirect_to = request.POST.get('redirect_to', 'list')
            URL_MAP = {
                'list':reverse('panel:list_candidatures'),
                'add_new':reverse('panel:create_candidature'),
                'edit':reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id})
            }
            return redirect(URL_MAP.get(redirect_to, 'list'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, level=40, message=error, extra_tags='danger')
            return redirect(reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id}))


@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def list_candidatures(request:HttpRequest):
    form = OscaryListCandidaturesForm()
    oscars = Oscar.objects.all().order_by('name')
    events = VotingEvent.objects.all().order_by('id')
    return render(request, 'panel/oscary/candidatures_list.html', context={
        'form':form,
        'oscars':oscars,
        'events':events
    })

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def partial_list_candidatures(request:HttpRequest):
    SORT_MAP = {
        'name':['teacher__first_name', 'teacher__second_name', 'teacher__last_name'],
        'creation':['created_at'],
        'update':['updated_at'],
        'id':['id']
    }
    FILTER_MAP = {
        'oscars':{
            'field':'oscar__id'
        },
        'events':{
            'field':'voting_round__voting_event__id'
        },
        'round_type':{
            'field':'voting_round__round_type'
        }
    }
    form = OscaryListCandidaturesForm(request.GET)
    form.is_valid()
    sort_data = build_sort_list(SORT_MAP, form.cleaned_data)
    filter_data = build_filter_kwargs(FILTER_MAP, form.cleaned_data)
    try:
        page_number = int(request.GET.get('page', 1))
    except ValueError:
        page_number = 1
    now = timezone.now()
    candidatures = Candidature.objects.select_related('oscar', 'teacher', 'voting_round', 'voting_round__voting_event')
    if form.cleaned_data.get('teacher_search', '') != '':
        vector = SearchVector('teacher__first_name', 'teacher__second_name', 'teacher__last_name')
        query = SearchQuery(form.cleaned_data['teacher_search'], search_type='websearch')
        candidatures = candidatures.annotate(rank=SearchRank(vector=vector, query=query)).filter(rank__gt=0, **filter_data).order_by('-rank', *sort_data['sort_fields'])
    else:
        candidatures = candidatures.filter(**filter_data).order_by(*sort_data['sort_fields'])
    paginator = Paginator(candidatures, 25)
    if page_number > paginator.num_pages:
        page_number = paginator.num_pages
    page_obj = paginator.get_page(page_number)
    params = request.GET.copy()
    params.pop('page', None)
    querystring = params.urlencode()
    return render(request, 'panel/oscary/partials/candidatures_list.html', context={
        'page_obj':page_obj,
        'querystring':querystring,
    })

@require_http_methods(['POST'])
@login_required(login_url='office_auth:microsoft_login')
@opiekun_required()
def delete_candidature(request:HttpRequest):
    """Widok usuwania wydarzenia głosowania. Działa zarówno dla statycznych formularzy jak i dynamicznych zapoytań HTMX"""
    candidature_id = request.POST.get('candidature_id')
    htmx = request.headers.get('HX-Request')
    if not candidature_id or not candidature_id.isdigit():
        return build_delete_feedback_response(request, type=ERROR, message="Nieprawidłowe ID kandydatury", redirect_url=reverse('panel:list_candidatures'))
    candidature = Candidature.objects.filter(id=candidature_id).first()
    if candidature:
        try:
            candidature.delete()
            return build_delete_feedback_response(request, type=SUCCESS, message='Pomyślnie usunięto kandydature', redirect_url=reverse('panel:list_candidatures'), alert_template=None)
        except ValidationError as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message=Ex,
                                                  redirect_url=reverse('panel:update_candidature',
                                                                       kwargs={'candidature_id': candidature_id}))
        except Exception as Ex:
            return build_delete_feedback_response(request, type=ERROR,
                                                  message='Wystąpił błąd podczas próby usunięcia kandydatury',
                                                  redirect_url=reverse('panel:update_teacher',
                                                                       kwargs={'candidature_id': candidature_id}))
    else:
        return build_delete_feedback_response(request, type=ERROR, message='Wystąpił błąd podczas próby usunięcia kandydatury', redirect_url=reverse('panel:update_candidature', kwargs={'candidature_id':candidature_id}))


