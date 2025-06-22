from django import forms
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.forms import formset_factory, BaseFormSet

import pytz

from .models import Voting, CandidateRegistration

class VoteForm(forms.Form):
    candidate_registration_id = forms.IntegerField()

    def __init__(self, *args, voting, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_voting = voting

    def clean(self):
        cleaned_data = super().clean()
        candidate_registration_id = cleaned_data.get('candidate_registration_id')
        try:
            registration_obj  = CandidateRegistration.objects.get(id=candidate_registration_id)
        except CandidateRegistration.DoesNotExist:
            raise ValidationError(f"Kandydatura o id: {candidate_registration_id} nie istnieje", code='candidature_does_not_exist')
        voting_id = registration_obj.voting.id
        if self.expected_voting.id != voting_id:
            raise ValidationError(f"Kandydatura o id: {candidate_registration_id} nie należy do obecnego głosowania", code='candidature_not_in_voting')


class BaseVoteFormSet(BaseFormSet):
    def __init__(self, *args, voting=None, **kwargs):
        self.voting = voting
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['voting'] = self.voting
        return super()._construct_form(i, **kwargs)

    def clean(self):
        super().clean()
        expected_vote_count = self.voting.votes_per_user
        filled_forms = 0
        for form in self.forms:
            # Sprawdź czy formularz jest wypełniony i poprawny
            if form.cleaned_data and form.cleaned_data.get('candidate_registration_id'):
                filled_forms += 1
        if filled_forms != expected_vote_count:
            raise ValidationError(
                f"Nie oddano wymaganej liczby głosów: {filled_forms}/{expected_vote_count}",
                code='invalid_form_count'
            )







