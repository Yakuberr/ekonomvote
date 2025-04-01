from django import forms
from .models import Voting
import pytz
from django.utils import timezone


class VotingForm(forms.Form):
    candidate_id = forms.IntegerField()
