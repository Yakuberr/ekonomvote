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

from collections import defaultdict
import pytz
import json

from office_auth.models import AzureUser

from .models import Voting, Candidate, Vote, ElectoralProgram, CandidateRegistration
from .forms import VoteForm, BaseVoteFormSet

# TODO: Dodać interaktywne usuwanie obiektów w panelu admina lub takie co zachowuje aktywne zmienne request.GET

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
    return render(request, 'samorzad_index.html', {
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
    return render(request, 'partials/old_votings_list.html', context={
        'page_num':page_num,
        'page_obj':page_obj,
        "has_next": page_obj.has_next()
    })


# QuerySet zliczania głosów dla poszczególnych kandydatur w ramach głosowania:
# Vote.objects.select_related('candidate_registration').filter(candidate_registration__voting=voting_id).values('candidate_registration').annotate(votes_count=Count('id'))

# TODO: Wrazie w usunąć pobieranie votingu z bazy danych w ramach oszczędzenia zapytań do bazy

# PARTIAL views

@require_http_methods(['GET'])
@login_required(login_url='office_auth:microsoft_login')
def get_timeline_data(request, voting_id):
    voting = get_object_or_404(Voting, pk=voting_id)
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

    # Struktura danych dla wykresu
    timeline_data = {
        "timeline": [],
        "candidates": defaultdict(lambda: {"votes": [], "name": ""})
    }
    vote_buckets = defaultdict(lambda: defaultdict(int)) # Godzinowe kubełki danych
    registrations = CandidateRegistration.objects.filter(
        voting=voting,
        is_eligible=True
    ).select_related('candidate').order_by('candidate__first_name', 'candidate__second_name', 'candidate__last_name')
    for reg in registrations:
        timeline_data["candidates"][reg.candidate.id]["name"] = \
            f"{reg.candidate.first_name} {reg.candidate.last_name}"

    # Grupowanie głosów do godzinowych kubełków
    for vote in votes:
        timestamp = vote.created_at.astimezone(
            pytz.timezone('Europe/Warsaw')
        ).replace(minute=0, second=0, microsecond=0)

        candidate_id = vote.candidate_registration.candidate.id
        vote_buckets[timestamp][candidate_id] += 1

    # Skumulowane liczenie głosów w czasie
    sorted_timestamps = sorted(vote_buckets.keys())
    vote_counts = defaultdict(int)

    for timestamp in sorted_timestamps:
        timeline_data["timeline"].append(timestamp.strftime("%Y-%m-%d %H:%M"))
        for cand_id in timeline_data["candidates"]:
            vote_counts[cand_id] += vote_buckets[timestamp].get(cand_id, 0)
            timeline_data["candidates"][cand_id]["votes"].append(vote_counts[cand_id])

    return render(request, 'experimental_timeline_template.html', context={
        'timeline_data':json.dumps(timeline_data, ensure_ascii=False),
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
    return render(request, 'experimental_chart_template.html', context={
        'results':json.dumps(results, ensure_ascii=False),
    })

# READ/CREATE views

@login_required(login_url='office_auth:microsoft_login')
@require_http_methods(["GET", "POST"])
def get_voting_details(request:HttpRequest, voting_id:int):
    voting = get_object_or_404(Voting, id=voting_id)
    can_vote = not request.user.is_superuser
    if request.method == 'GET':
        user_has_voted = CandidateRegistration.objects.filter(voting=voting.id,
                                                              votes__microsoft_user=request.user).exists()
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
        winner_id = CandidateRegistration.objects.filter(voting=voting.id).annotate(votes_count=Count('votes')).order_by(
            '-votes_count').only('id').first().id
        return render(request, 'voting_details.html', context={
            'voting':voting,
            'registrations':registrations,
            'votes_count':votes_count,
            'user_has_voted':user_has_voted,
            'can_vote':can_vote,
            'winner_id':winner_id,
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



# TODO: Naprawić docelowy URL dla kodu qr
# TODO: Dodać warunek w templace dla samorzad:get_voting_details żeby stronę inaczej jeśli nie ma aktywnych kandydatów
# TODO Sprawdzić czemu w niektórych głosowania z jedną kandydaturą nie widać kandydatury
# TODO: Prowadzący kandydat może być uwidoczniony tylko po zagłosowaniu
# TODO: w templatce samorzad_index należy zmienić text renderowany w kodzie qr na url odnoszące się do głosowania


