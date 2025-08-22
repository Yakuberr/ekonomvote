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
from oscary.models import VotingEvent, Oscar, Teacher, Candidature, VotingRound
from .bleach_config import ALLOWED_TAGS, ALLOWED_ATTRIBUTES, css_sanitizer

MAX_IMAGE_SIZE_MB = 2

def _convert_tz(value):
    if value is not None:
        value: timezone.datetime
        naive_value = value.replace(tzinfo=None)
        warsaw = pytz.timezone('Europe/Warsaw')
        aware_value = warsaw.localize(naive_value)
        return aware_value.astimezone(pytz.UTC)

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
        return _convert_tz(value)

    def clean_planned_end(self):
        value = self.cleaned_data.get('planned_end')
        return _convert_tz(value)


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
            strip=True,
            css_sanitizer=css_sanitizer
        )
        cleaned = bleach.linkify(cleaned)
        return cleaned

# Oscary

class OscaryAddWholeVotingEventForm(forms.Form):
    with_nominations = forms.BooleanField(required=False, error_messages={
        'invalid':"Błedna wartość dla pola określającego nominację"
    })
    f_round_t_count = forms.IntegerField(min_value=1, required=False, error_messages={
        'invalid':"Błędna wartość pola zwycięzkich nauczycieli"
    })
    f_round_start = forms.DateTimeField(required=False, error_messages={
        'invalid':"Błędna wartość dla daty startu nominacji"
    })
    f_round_end = forms.DateTimeField(required=False, error_messages={
        'invalid':"Błędna wartość dla daty końca nominacji"
    })
    l_round_start = forms.DateTimeField(required=True, error_messages={
        'invalid':"Błędna wartość dla daty startu rundy finałowej",
        'required':"Data startu rundy finałowej musi być podana"
    })
    l_round_end = forms.DateTimeField(required=True, error_messages={
        'invalid':"Błędna wartość dla daty końca rundy finałowej",
        'required': "Data końca rundy finałowej musi być podana"
    })

    def clean_with_nominations(self):
        val = self.cleaned_data.get('with_nominations')
        if type(val) is not bool:
            raise ValidationError("Nieprawidłowy typ danych.", code='bad_data_type')
        return val

    def clean_f_round_start(self):
        value = self.cleaned_data.get('f_round_start')
        try:
            return _convert_tz(value)
        except (AttributeError, ValueError):
            raise ValidationError("Nie udało się przekonwertować daty", code='bad_data_type')

    def clean_f_round_end(self):
        value = self.cleaned_data.get('f_round_end')
        try:
            return _convert_tz(value)
        except (AttributeError, ValueError):
            raise ValidationError("Nie udało się przekonwertować daty", code='bad_data_type')

    def clean_l_round_start(self):
        value = self.cleaned_data.get('l_round_start')
        try:
            return _convert_tz(value)
        except (AttributeError, ValueError):
            raise ValidationError("Nie udało się przekonwertować daty", code='bad_data_type')

    def clean_l_round_end(self):
        value = self.cleaned_data.get('l_round_end')
        try:
            return _convert_tz(value)
        except (AttributeError, ValueError):
            raise ValidationError("Nie udało się przekonwertować daty", code='bad_data_type')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('with_nominations') and None in [cleaned_data.get('f_round_t_count'), cleaned_data.get('f_round_start'), cleaned_data.get('f_round_end')]:
            raise ValidationError("Brak pól związanych z nominacją", code='fields_required')


class OscaryListVotingsForm(forms.Form):
    sort_by = forms.ChoiceField(choices=[
        ('id', 'ID'),
        ('nomination_start', 'Start nominacji'),
        ('final_start', 'Start finału'),
        ('creation', 'Data utworzenia'),
        ('update', 'Data aktualizacji')
    ], initial='id', required=False)

    sort_order = forms.ChoiceField(choices=[
        ('asc', 'Rosnąco'),
        ('desc', 'Malejąco')
    ], initial='asc', required=False)

    event_status = forms.CharField(required=False)

    nominations = forms.ChoiceField(choices=[
        ('yes', 'Tak'),
        ('no', 'Nie')
    ], required=False)

    def clean_sort_by(self):
        value = self.cleaned_data.get('sort_by')
        if value not in [choice[0] for choice in self.fields['sort_by'].choices]:
            value = 'id'
        return value

    def clean_sort_order(self):
        value = self.cleaned_data.get('sort_order')
        if value not in [choice[0] for choice in self.fields['sort_order'].choices]:
            value = 'asc'
        return value

    def clean_event_status(self):
        ALLOWED_VALUES =  ['Zaplanowane', "Aktywne", "Zakończone"]
        values = self.cleaned_data.get('event_status', '').split(',')
        for param in values:
            if param not in ALLOWED_VALUES:
                return None
        return values


    def clean_nominations(self):
        CONVERT_MAP = {
            'yes':True,
            'no':False
        }
        value = self.cleaned_data.get('nominations')
        if value not in [choice[0] for choice in self.fields['nominations'].choices]:
            value = None
        else:
            try:
                value = CONVERT_MAP[value]
            except KeyError:
                value = None
        return value

class OscaryCreateOscarForm(forms.ModelForm):
    class Meta:
        model = Oscar
        fields = ['name', 'info']

class OscaryListOscarsForm(forms.Form):
    sort_by = forms.ChoiceField(choices=[
        ('id', 'ID'),
        ('name', 'Nazwa'),
        ('creation', 'Data utworzenia'),
        ('update', 'Data aktualizacji')
    ], initial='id', required=False)

    sort_order = forms.ChoiceField(choices=[
        ('asc', 'Rosnąco'),
        ('desc', 'Malejąco')
    ], initial='asc', required=False)

    search = forms.CharField(max_length=2048 ,error_messages={
        'max_length':'Można podać maksymalnie 2048 znaków'
    }, required=False)

class OscaryCreateTeacher(forms.ModelForm):
    class Meta:
        model = Teacher
        fields = ['first_name', 'second_name', 'last_name', 'info', 'image']

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

class OscaryListTeachersForm(forms.Form):
    sort_by = forms.ChoiceField(choices=[
        ('id', 'ID'),
        ('name', 'Nazwa'),
        ('creation', 'Data utworzenia'),
        ('update', 'Data aktualizacji')
    ], initial='id', required=False)

    sort_order = forms.ChoiceField(choices=[
        ('asc', 'Rosnąco'),
        ('desc', 'Malejąco')
    ], initial='asc', required=False)

    search = forms.CharField(max_length=2048 ,error_messages={
        'max_length':'Można podać maksymalnie 2048 znaków'
    }, required=False)

class OscaryCreateCandidatureForm(forms.ModelForm):
    class Meta:
        model = Candidature
        fields = ['oscar', 'teacher', 'voting_round']

class OscaryListCandidaturesForm(forms.Form):
    teacher_search = forms.CharField(max_length=2048, required=False, error_messages={
        'max_length':"Do wyszukiwarki można wprowadzić maksymalnie 2048 znaków"
    })

    sort_order = forms.ChoiceField(choices=[
        ('asc', 'Rosnąco'),
        ('desc', 'Malejąco')
    ], initial='asc', required=False)

    sort_by = forms.ChoiceField(choices=[
        ('id', 'ID'),
        ('name', 'Imionach'),
        ('creation', 'Data utworzenia'),
        ('update', 'Data aktualizacji')
    ], initial='id', required=False)

    round_type = forms.ChoiceField(choices=(
        (VotingRound.VotingRoundType.NOMINATION, VotingRound.VotingRoundType.NOMINATION.label),
        (VotingRound.VotingRoundType.FINAL, VotingRound.VotingRoundType.FINAL.label),
    ), required=False, error_messages={
        'invalid':"Podaj prawidłową wartość filtra rund"
    }, initial=None)

    oscars = forms.IntegerField(required=False, error_messages={
        'invalid':"Podaj prawidłową wartość filtra oscarów"
    })
    events = forms.IntegerField(required=False, error_messages={
        'invalid':"Podaj prawidłową wartość filtra wydarzeń"
    })

    def clean_round_type(self):
        value = self.cleaned_data.get('round_type')
        if value == '': return None
        return value










