from django.shortcuts import render, redirect, reverse
from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponse
from django.utils import timezone, dateparse
from django.contrib import messages
from django.core.exceptions import ValidationError
from office_auth.views import azure_login_required
from samorzad.models import Voting, Candidate, Vote
from .forms import VotingForm

@azure_login_required
def list_votings(request:HttpRequest):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    fresh_voting = Voting.objects.filter(planned_end__gt = timezone.now()).order_by('planned_start').first()
    old_votings = Voting.objects.filter(planned_end__lt = timezone.now())
    return render(request, 'index.html', context={'fresh_voting':fresh_voting, 'old_votings':old_votings})

@azure_login_required
def get_voting_details(request:HttpRequest, id:int):
    if request.method not in ['GET', 'POST']:
        return HttpResponseNotAllowed(["GET"])
    return HttpResponse(f'Id podane w adresie: {id}')

@azure_login_required
def post_vote(request:HttpRequest):
    fresh_voting_pk = Voting.objects.filter(planned_end__gt=timezone.now()).order_by('planned_start').first().pk
    candidates = Candidate.objects.filter(is_eligible=True).order_by('first_name', 'second_name', 'last_name')
    if request.method == 'GET':
        voted = Vote.objects.filter(azure_user_id=request.session.get('microsoft_user_id'), voting__pk=fresh_voting_pk).exists()
        form = VotingForm()
        return render(request, 'vote.html', context={'fresh_voting_pk':fresh_voting_pk, 'candidates':candidates, 'form':form, 'voted':voted})
    if request.method == 'POST':
        form = VotingForm(request.POST)
        if form.is_valid():
            candidate_id = form.cleaned_data.get('candidate_id')
            if candidate_id is None:
                messages.error('Nieprawidłowy kandydat')
                return redirect(reverse('samorzad:post_vote'))
            if fresh_voting_pk is None:
                messages.error('Nieprawidłowy kandydat')
                return redirect(reverse('samorzad:post_vote'))
            try:
                Vote.objects.create(
                    azure_user_id=request.session.get('microsoft_user_id'),
                    candidate=Candidate.objects.filter(is_eligible=True, pk=candidate_id).first(),
                    voting=Voting.objects.filter(pk=fresh_voting_pk).first()
                )
            except ValidationError:
               return redirect(reverse('samorzad:post_vote'))
            return redirect(reverse('samorzad:index'))
        # TODO: Obsłużyć błąd walidacji


