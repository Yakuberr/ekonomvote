from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponse,  HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.utils import timezone, dateparse
from django.contrib import messages
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.db.models import F, Exists, OuterRef, Q
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.forms import formset_factory
from django.utils.timezone import datetime, timedelta

from collections import defaultdict
import pytz
import json

from office_auth.models import AzureUser
from office_auth.auth_utils import is_opiekun
from .models import Voting, Candidate, Vote, ElectoralProgram, CandidateRegistration
from .forms import VoteForm, BaseVoteFormSet


@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
def list_votings(request: HttpRequest):
    now = timezone.now()
    fresh_voting = Voting.objects.filter(
        planned_start__lte=now,
        planned_end__gt=now
    ).annotate(
        votes_count=Count('candidate_registrations__votes', distinct=True)
    ).annotate(
        registrations_count=Count('candidate_registrations', filter=Q(candidate_registrations__is_eligible=True), distinct=True)
    ).order_by('planned_start').first()
    return render(request, 'samorzad/samorzad_index.html', {
        'fresh_voting': fresh_voting,
    })

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(['GET'])
def partial_list_old_votings(request:HttpRequest):
    try:
        page_num = int(request.GET.get('page', 1))
    except ValueError:
        page_num = 1
    now = timezone.now()
    old_votings = Voting.objects.filter(
        planned_end__lte=now
    ).annotate(
        candidates_count=Count('candidate_registrations', filter=Q(candidate_registrations__is_eligible=True), distinct=True),
        votes_count=Count('candidate_registrations__votes', distinct=True)
    ).order_by('-planned_end')
    paginator = Paginator(old_votings, 9)
    page_obj = paginator.get_page(page_num)
    return render(request, 'samorzad/partials/old_votings_list.html', context={
        'page_num':page_num,
        'page_obj':page_obj,
        "has_next": page_obj.has_next()
    })



# PARTIAL views
# Widok powinno się cachować
@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
def get_timeline_data(request, voting_id):
    voting = get_object_or_404(Voting, pk=voting_id)
    warsaw_tz = pytz.timezone('Europe/Warsaw')

    # Określenie pełnego zakresu czasowego
    start_time = voting.planned_start.astimezone(warsaw_tz).replace(minute=0, second=0, microsecond=0)
    if voting.planned_end <= timezone.now():
        current_time = voting.planned_end.astimezone(warsaw_tz).replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1)
    else:
        current_time = datetime.now(warsaw_tz).replace(minute=0, second=0, microsecond=0)


    # Generowanie wszystkich godzin w zakresie (kluczowe dla Chart.js!)
    all_hours = []
    current_hour = start_time
    while current_hour <= current_time:
        all_hours.append(current_hour)
        current_hour += timedelta(hours=1)

    votes = Vote.objects.filter(
        candidate_registration__voting=voting.id
    ).select_related(
        'candidate_registration__candidate'
    ).only(
        'created_at',
        'candidate_registration__id',
        'candidate_registration__candidate__id',
        'candidate_registration__candidate__first_name',
        'candidate_registration__candidate__last_name'
    ).order_by('created_at')

    # Struktura danych dla Chart.js
    timeline_data = {
        "timeline": [],
        "candidates": {}
    }

    # Inicjalizacja wszystkich kandydatów
    registrations = CandidateRegistration.objects.filter(
        voting=voting,
        is_eligible=True
    ).select_related('candidate').order_by('candidate__first_name', 'candidate__last_name')

    for reg in registrations:
        timeline_data["candidates"][reg.candidate.id] = {
            "name": f"{reg.candidate.first_name} {reg.candidate.last_name}",
            "votes": []  # Będzie miał dokładnie len(all_hours) elementów
        }

    # Grupowanie głosów do godzinowych kubełków
    vote_buckets = defaultdict(lambda: defaultdict(int))
    for vote in votes:
        timestamp = vote.created_at.astimezone(warsaw_tz).replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(hours=1)
        candidate_id = vote.candidate_registration.candidate.id
        vote_buckets[timestamp][candidate_id] += 1

    # KLUCZOWE: Budowanie timeline dla WSZYSTKICH godzin
    vote_counts = defaultdict(int)  # Skumulowane liczniki

    for timestamp in all_hours:
        # Dodaj godzinę do timeline
        timeline_data["timeline"].append(timestamp.strftime("%Y-%m-%d %H:%M"))

        # Dla każdego kandydata dodaj głosy z tej godziny i zaktualizuj skumulowaną wartość
        for cand_id in timeline_data["candidates"]:
            # Dodaj głosy z tej konkretnej godziny (0 jeśli brak)
            vote_counts[cand_id] += vote_buckets[timestamp].get(cand_id, 0)
            # Dodaj skumulowaną wartość do tablicy (zawsze!)
            timeline_data["candidates"][cand_id]["votes"].append(vote_counts[cand_id])

    # Weryfikacja: wszystkie tablice muszą mieć tę samą długość
    timeline_length = len(timeline_data["timeline"])
    for cand_id, cand_data in timeline_data["candidates"].items():
        assert len(cand_data["votes"]) == timeline_length, f"Kandydat {cand_id} ma nieprawidłową długość danych"

    return render(request, 'samorzad/experimental_timeline_template.html', context={
        'timeline_data': json.dumps(timeline_data, ensure_ascii=False),
    })

@require_http_methods(["GET"])
@login_required(login_url='office_auth:microsoft_login')
def get_chart_data(request:HttpRequest, voting_id:int):
    voting = get_object_or_404(Voting, pk=voting_id)
    registrations = CandidateRegistration.objects.filter(
        voting=voting,
        is_eligible=True
    ).prefetch_related(
        'votes'
    ).select_related('candidate').annotate(
        votes_count=Count('votes')
    ).order_by('candidate__first_name', 'candidate__last_name')
    total_votes = Vote.objects.filter(
        candidate_registration__voting=voting
    ).count()
    results = []
    for reg in registrations.select_related('candidate'):
        percentage = (reg.votes_count / total_votes * 100) if total_votes > 0 else 0
        results.append({
            "candidate": {
                'first_name':reg.candidate.first_name,
                'second_name':reg.candidate.second_name,
                'last_name':reg.candidate.last_name,
                'school_class':reg.candidate.school_class
            },
            "votes_count": reg.votes_count,
            "percentage": round(percentage, 2),
        })
    results.sort(key=lambda d:d['votes_count'], reverse=True)
    return render(request, 'samorzad/experimental_chart_template.html', context={
        'results':json.dumps(results, ensure_ascii=False),
    })

# READ/CREATE views

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(["GET", "POST"])
def get_voting_details(request:HttpRequest, voting_id:int):
    voting = get_object_or_404(Voting, id=voting_id)
    can_vote = not is_opiekun(request.user)
    if request.method == 'GET':
        user_has_voted = CandidateRegistration.objects.filter(voting=voting.id,
                                                              votes__microsoft_user=request.user).exists() or is_opiekun(request.user)
        votes_count = Vote.objects.select_related('candidate_registration').filter(
            candidate_registration__voting=voting).count()
        registrations = CandidateRegistration.objects.filter(
            voting=voting,
            is_eligible=True
        ).select_related('candidate', 'electoral_program').order_by('candidate__first_name', 'candidate__second_name',
                                                                    'candidate__last_name').annotate(
            # Sprawdza czy użytkownik zagłosował na danego kandydata
            has_voted=Exists(
                Vote.objects.filter(
                    candidate_registration=OuterRef('pk'),
                    microsoft_user=request.user
                )
            )
        ).order_by('candidate__first_name', 'candidate__second_name', 'candidate__last_name')
        # TODO: winner_id musi byc poprawiony (ma działać tylko po zakończeniu głosowania)
        # TODO: Jeśli nie ma zrejestrowanych legalnych kandydatur to nie wysyłać requestów po wykresy
        # winner_id = CandidateRegistration.objects.filter(voting=voting.id).annotate(votes_count=Count('votes')).order_by(
        #     '-votes_count').only('id').first().id
        return render(request, 'samorzad/voting_details.html', context={
            'voting':voting,
            'registrations':registrations,
            'votes_count':votes_count,
            'user_has_voted':user_has_voted,
            'can_vote':can_vote,
            #'winner_id':winner_id,
        })
    if request.method == 'POST':
        if not can_vote:
            return HttpResponseForbidden()
        VoteFormFactory = formset_factory(
            VoteForm,
            formset=BaseVoteFormSet,
            extra=voting.votes_per_user
        )
        formset = VoteFormFactory(request.POST, voting=voting)
        if formset.is_valid():
            for form in formset:
                vote_data = form.cleaned_data
                Vote.objects.create(
                    candidate_registration_id = vote_data['candidate_registration_id'],
                    microsoft_user=request.user
                )
        else:
            for error in formset.non_form_errors():
                messages.error(request, error)
            for form_errors in formset.errors:
                for field, errors in form_errors.items():
                    for error in errors:
                        messages.error(request, error)
        return redirect(reverse('samorzad:get_voting_details', kwargs={'voting_id':voting.id}))



# TODO: Dodać warunek w templace dla samorzad:get_voting_details żeby stronę inaczej jeśli nie ma aktywnych kandydatów
# TODO: Prowadzący kandydat może być uwidoczniony tylko po zagłosowaniu


