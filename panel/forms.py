from django import forms
from django.forms import inlineformset_factory
from django.core.exceptions import ValidationError
from django.utils import timezone

from PIL import Image
import string
import pytz
import re
import bleach

from samorzad.models import Voting, Candidate, CandidateRegistration, ElectoralProgram
from .bleach_config import ALLOWED_TAGS, ALLOWED_ATTRIBUTES

MAX_IMAGE_SIZE_MB = 2

class PanelLoginForm(forms.Form):
    login = forms.CharField(min_length=1, max_length=1024, empty_value='N/A')
    password = forms.CharField(min_length=8, max_length=1024, empty_value='')

    def clean(self):
        super().clean()
        password = self.cleaned_data.get('password')
        if password is None:
            password = ''
        has_lower = any(c in string.ascii_lowercase for c in password)
        has_upper = any(c in string.ascii_uppercase for c in password)
        has_digit = any(c in string.digits for c in password)
        has_special = any(c in string.punctuation for c in password)
        if not (has_lower and has_upper and has_digit and has_special):
            raise ValidationError("Hasło musi mieć minimum 8 znaków zawierać małe i duże litery, cyfrę oraz znak specjalny.")
        return self.cleaned_data

class SamorzadAddEmptyVotingForm(forms.ModelForm):
    class Meta:
        model=Voting
        fields=['votes_per_user', 'planned_start', 'planned_end']

    def clean_votes_per_user(self):
        value = int(self.cleaned_data.get('votes_per_user'))
        if value < 1:
            raise ValidationError("Ilość głosów musi być większa od 0")
        return value

    def clean_planned_start(self):
        value = self.cleaned_data.get('planned_start')
        value:timezone.datetime
        naive_value = value.replace(tzinfo=None)
        warsaw = pytz.timezone('Europe/Warsaw')
        aware_value = warsaw.localize(naive_value)
        return aware_value.astimezone(pytz.UTC)

    def clean_planned_end(self):
        value = self.cleaned_data.get('planned_end')
        value:timezone.datetime
        naive_value = value.replace(tzinfo=None)
        warsaw = pytz.timezone('Europe/Warsaw')
        aware_value = warsaw.localize(naive_value)
        return aware_value.astimezone(pytz.UTC)


class SamorzadAddCandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        exclude = ['created_at', 'updated_at']

    def clean_school_class(self):
        value = self.cleaned_data.get('school_class')
        if value is None:
            raise ValidationError('Klasa nie może być pusta')
            return value
        value = value.upper()
        if re.match(r'\d.[A-Z]{2,3}', value) is None:
            raise ValidationError(f'Klasa kandydata powinna być w formacie: numer symbol np: 5 ti')
        return value

    def clean_second_name(self):
        value = self.cleaned_data.get('second_name')
        if value is None:
            value = ''
        return value

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
                raise ValidationError(f"Zdjęcie nie może być większe niż {MAX_IMAGE_SIZE_MB}MB.")
            try:
                img = Image.open(image)
                if img.size != (400, 400):
                    raise ValidationError("Zdjęcie musi mieć dokładnie 400x400 pikseli.")
            except Exception:
                raise ValidationError("Nie udało się przetworzyć obrazu. Upewnij się, że to poprawny plik graficzny.")
        return image

class CandidateRegistrationForm(forms.ModelForm):
    class Meta:
        model = CandidateRegistration
        fields = ['candidate', 'voting', 'is_eligible']


class ElectoralProgramForm(forms.ModelForm):
    class Meta:
        model = ElectoralProgram
        fields = ['info']

    def clean_info(self):
        value = self.cleaned_data.get('info')
        cleaned = bleach.clean(
            value,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            strip=True
        )
        cleaned = bleach.linkify(cleaned)
        return cleaned


ElectoralProgramFormSet = inlineformset_factory(
    CandidateRegistration,
    ElectoralProgram,
    form=ElectoralProgramForm,
    fields=['info'],
    extra=1,
    can_delete=False,
    min_num=1,
    validate_min=True
)




