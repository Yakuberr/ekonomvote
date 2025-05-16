from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone, dateparse
from django.contrib import messages
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.db.models import F
from office_auth.models import AzureUser
from .models import Voting, Candidate, Vote, ElectoralProgram, CandidateRegistration
from .forms import VotingForm


@login_required(login_url='office_auth:microsoft_login')
def list_votings(request: HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    now = timezone.now()
    fresh_voting = Voting.objects.filter(
        planned_start__lte=now,
        planned_end__gt=now
    ).annotate(
        votes_count=Count('candidate_registrations__votes', distinct=True)
    ).order_by('planned_start').first()
    old_votings = Voting.objects.filter(
        planned_end__lte=now
    ).annotate(
        candidates_count=Count('candidate_registrations', distinct=True),
        votes_count=Count('candidate_registrations__votes', distinct=True)
    ).order_by('-planned_end')
    return render(request, 'index.html', {
        'fresh_voting': fresh_voting,
        'old_votings': old_votings
    })


@login_required(login_url='office_auth:microsoft_login')
def get_voting_details(request: HttpRequest, id: int):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(["GET"])
    voting = get_object_or_404(
        Voting.objects.annotate(
            total_votes=Count('candidate_registrations__votes')
        ),
        pk=id
    )
    if voting.candidate_registrations.count() == 0:
        messages.error(
            request,
            f'Głosowanie rozpoczęte {voting.parse_planned_start()} nie zostało poprawnie przeprowadzone'
        )
        return redirect(reverse('samorzad:index'))
    vote = Vote.objects.filter(
        azure_user=request.user,
        candidate_registration__voting=voting
    ).select_related('candidate_registration__candidate').first()
    if vote is None:
        messages.error(request, 'Nie można podejrzeć wyników przed zagłosowaniem')
        return redirect(reverse('samorzad:post_vote'))
    candidates = CandidateRegistration.objects.filter(
        voting_id=id,
        is_eligible=True
    ).annotate(
        candidate_votes=Count('votes'),  # Głosy per kandydat
        first_name=F('candidate__first_name'),
        last_name=F('candidate__last_name'),
        program=F('candidate__electoral_programs__info'),
        image_url=F('candidate__image'),
        school_class=F('candidate__school_class')
    ).order_by('-candidate_votes')
    return render(request, 'voting_details.html', {
        'voting': voting,
        'candidates': candidates,
        'total_votes': voting.total_votes  # Przekazanie łącznej liczby głosów do szablonu
    })


@login_required(login_url='office_auth:microsoft_login')
def post_vote(request: HttpRequest):
    fresh_voting = Voting.objects.filter(planned_end__gt=timezone.now()).order_by('planned_start').first()
    if not fresh_voting:
        messages.error(request, 'Brak aktywnego głosowania')
        return redirect(reverse('samorzad:index'))
    registrations = CandidateRegistration.objects.filter(
        voting=fresh_voting,
        is_eligible=True
    ).select_related('candidate').prefetch_related('candidate__electoral_programs').order_by('candidate__first_name', 'candidate__last_name')
    candidates_data = []
    for reg in registrations:
        electoral_program = reg.candidate.electoral_programs.filter(
            voting=fresh_voting
        ).first()
        candidates_data.append({
            'pk': reg.candidate.pk,
            'registration_pk': reg.pk,
            'first_name': reg.candidate.first_name,
            'last_name': reg.candidate.last_name,
            'image': reg.candidate.image,
            'program_info': electoral_program.info if electoral_program else "Brak programu",
            'school_class':reg.candidate.school_class
        })
    if request.method == 'GET':
        voted = Vote.objects.filter(
            azure_user = request.user,
            candidate_registration__voting=fresh_voting
        ).exists()
        posted_vote = None
        if voted:
            vote = Vote.objects.filter(
                azure_user=request.user,
                candidate_registration__voting=fresh_voting
            ).select_related('candidate_registration__candidate').first()
            if vote:
                candidate = vote.candidate_registration.candidate
                posted_vote = {
                    'first_name': candidate.first_name,
                    'last_name': candidate.last_name
                }
        return render(request, 'vote.html', {
            'candidates': candidates_data,
            'voted': voted,
            'posted_vote': posted_vote
        })
    if request.method == 'POST':
        if request.user.microsoft_user_id is None:
            messages.error(request, 'Głosować mogą tylko konta zalogowane poprzez office')
            redirect(reverse('samorzad:post_vote'))
        form = VotingForm(request.POST)
        if form.is_valid():
            registration_id = form.cleaned_data.get('registration_id')
            try:
                registration = CandidateRegistration.objects.get(
                    pk=registration_id,
                    voting=fresh_voting,
                    is_eligible=True
                )
                Vote.objects.create(
                    azure_user=request.user,
                    candidate_registration=registration
                )
                messages.success(request, 'Dziękujemy za oddanie głosu')
                return redirect(reverse('samorzad:index'))
            except (CandidateRegistration.DoesNotExist, ValidationError):
                messages.error(request, 'Nie można oddać głosu na tego kandydata')
        else:
            messages.error(request, 'Nieprawidłowe dane formularza')
        return redirect(reverse('samorzad:post_vote'))


