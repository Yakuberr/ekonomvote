from django import forms
from .models import Voting
import pytz
from django.utils import timezone


class VotingForm(forms.Form):
    candidate_id = forms.IntegerField()

class VotingForm(forms.Form):
    registration_id = forms.IntegerField(required=True)
