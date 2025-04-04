from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponse
from django.utils import timezone, dateparse
from django.contrib import messages
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.db.models import F
from office_auth.views import azure_login_required
from .models import Voting, Candidate, Vote, ElectoralProgram, CandidateRegistration
from .forms import VotingForm


@azure_login_required
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


@azure_login_required
def get_voting_details(request: HttpRequest, id: int):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(["GET"])
    voting = get_object_or_404(Voting, pk=id)
    voting = Voting.objects.filter(pk=id)
    top_candidate_id = Vote.objects.filter(candidate_registration__voting_id=id).values('candidate_registration__candidate_id').annotate(count=Count('id')) \
        .order_by('-count') \
        .values_list('candidate_registration__candidate_id', flat=True) \
        .first()
    q = Vote.objects.filter(candidate_registration__voting_id=id) \
    .values('candidate_registration__candidate') \
    .annotate(
        count=Count('id'),
        first_name=F('candidate_registration__candidate__first_name'),
        last_name=F('candidate_registration__candidate__last_name'),
        program=F('candidate_registration__candidate__electoral_programs__info'),
        image_url=F('candidate_registration__candidate__image')
    ) \
    .filter(candidate_registration__candidate__electoral_programs__voting_id=id) \
    .order_by('-count')
    voting = voting.annotate(votes_count=Count('candidate_registrations__votes', distinct=True)).first()
    if voting.votes_count == 0 and top_candidate_id is None:
        messages.error(request, f'Głosowanie rozpoczęte {voting.parse_planned_start()} nie zostało poprawnie przeprowadzone')
        return redirect(reverse('samorzad:index'))
    return render(request, 'voting_details.html', {
        'voting': voting,
        'candidates':q
    })


@azure_login_required
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
            'program_info': electoral_program.info if electoral_program else "Brak programu"
        })
    if request.method == 'GET':
        voted = Vote.objects.filter(
            azure_user_id=request.session.get('microsoft_user_id'),
            candidate_registration__voting=fresh_voting
        ).exists()
        posted_vote = None
        if voted:
            vote = Vote.objects.filter(
                azure_user_id=request.session.get('microsoft_user_id'),
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
                    azure_user_id=request.session.get('microsoft_user_id'),
                    candidate_registration=registration
                )
                messages.success(request, 'Dziękujemy za oddanie głosu')
                return redirect(reverse('samorzad:index'))
            except (CandidateRegistration.DoesNotExist, ValidationError):
                messages.error(request, 'Nie można oddać głosu na tego kandydata')
        else:
            messages.error(request, 'Nieprawidłowe dane formularza')
        return redirect(reverse('samorzad:post_vote'))


