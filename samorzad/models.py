from django.db import models
from django.utils import timezone, dateparse
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.exceptions import ObjectDoesNotExist
from office_auth.models import AzureUser

from auditlog.registry import auditlog
import pytz

class Voting(models.Model):
    """
    Model reprezentujący głosowanie, pola:

    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    - planned_start: Czas rozpoczęcia głosowania (UTC)
    - planned_end: Czas zakończenia głosowania (UTC)
    - votes_per_user: Dodatnia liczba, która reprezentuje liczbę głosów które można oddać na poszczególnych kandydatów
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='data utworzenia')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='data aktualizacji')
    planned_start = models.DateTimeField(null=False, verbose_name='data startu')
    planned_end = models.DateTimeField(null=False, verbose_name='data końca')
    votes_per_user = models.SmallIntegerField(
        default=1,
        validators=[MinValueValidator(1, 'Ilość głosów musi być większa od 0')],
        verbose_name='głosów na użytkownika'
    )

    class Meta:
        verbose_name="Głosowanie"
        verbose_name_plural = 'Głosowania'

    def parse_planned_start(self):
        """Zwraca planned_start w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_planned_end(self):
        """Zwraca planned_end w formacie polskiej strefy czasowej w postaci stringa"""
        return self.planned_end.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("Głosowanie musi zaczynać się później niż obecna data.", code='invalid_planned_start_value')
        if self.planned_start >= self.planned_end:
            raise ValidationError("Głosowanie musi kończyć się później niż jego data rozpoczęcia.", code='invalid_planned_end_value')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Voting(start={self.parse_planned_start()}, end={self.parse_planned_end()})'

auditlog.register(Voting)

class Candidate(models.Model):
    """Model reprezentujący kandydata na wybory do samorządu, pola:

    - first_name: Imię kandydata
    - second_name: Drugie imię kandydata, domyślnie pusty string
    - last_name: Nazwisko kandydata
    - image: Zdjęcie kandydata, może być null
    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    - school_class: Klasa kandydata w obecnych wyborach, może być null ale nie powinna
    """
    first_name = models.CharField(null=False, max_length=150, verbose_name='imię')
    second_name = models.CharField(default="", max_length=150, blank=True, verbose_name='drugie imię')
    last_name = models.CharField(null=False, max_length=150, verbose_name='nazwisko')
    image = models.ImageField(upload_to='uploads/samorzad/', null=True, blank=True, unique=False, verbose_name='zdjęcie')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='data utworzenia')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='data aktualizacji')
    school_class = models.CharField(max_length=20, verbose_name='klasa')

    class Meta:
        verbose_name="Kandydat"
        verbose_name_plural = 'Kandydaci'

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def __str__(self):
        return f'Candiate(first_name={self.first_name}, last_name={self.last_name})'

auditlog.register(Candidate)

class ElectoralProgram(models.Model):
    """
    Model reprezentujący program wyborczy kandydata w wyborach. Każdy kandydat może mieć różne programy wyborcze w różnych głosowaniach
    ALE może mieć tylko 1 program wyborczy w konkretnym głosowaniu (class Meta), pola:

    - candidate: Klucz obcy kandydata
    - voting: Klucz obcy głosowania
    - info: Tekst programu wyborczego
    - created_at: Czas utworzenia obiektu (strefa UTC)
    - updated_at: Czas aktualizacji obiektu (strefa UTC)
    """
    candidature = models.OneToOneField('CandidateRegistration', on_delete=models.CASCADE, related_name='electoral_program', verbose_name='kandydatura')
    info = models.TextField(null=False, verbose_name='program wyborczy',error_messages={
        'blank':"Zawartość programu wyborczego jest wymagana",
        'null':"Zawartość programu wyborczego nie może być pusta",
        'required':"Zawartość programu wyborczego jest wymagana",
    })
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='data utworzenia')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='data aktualizacji')

    class Meta:
        verbose_name="Program wyborczy"
        verbose_name_plural = 'Programy wyborcze'


    def __str__(self):
        return f'ElectoralProgram(candidature={self.candidature.pk})'

auditlog.register(ElectoralProgram)


class CandidateRegistration(models.Model):
    """Model n..n łączący modele kandydata i głosowania, pola:

    - candidate: Klucz obcy modelu kandydata
    - voting: Klucz obcy modelu głosowania
    - is_eligible: Boolean określający czy kandydat jest dopuszczony go głosowania
    - created_at: Czas utworzenia obiektu (strefa UTC)
    """
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='registrations', verbose_name='kandydat')
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='candidate_registrations', verbose_name='głosowanie')
    is_eligible = models.BooleanField(default=False, verbose_name='dopuszczony do wyborów')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='data utworzenia')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='data aktualizacji')

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    def parse_updated_at(self):
        return self.updated_at.astimezone(tz=pytz.timezone('Europe/Warsaw'))

    class Meta:
        # Zapobiega duplikatom
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_candidate_per_voting',
            violation_error_message="Kandydatura dla tego kandydata już istnieje w tym głosowaniu")
        ]
        verbose_name="Kandydatura"
        verbose_name_plural = 'Kandydatury'

    def __str__(self):
        return f'CandidateRegistration(candidate={self.candidate.pk}, voting={self.voting.pk})'

    def clean(self):
        try:
            voting = self.voting
        except ObjectDoesNotExist:
            raise ValidationError("Podane głosowanie nie istnieje w systemie.", code='voting_does_not_exist')
        # TODO: O tą zmienną trzeba się pytać lecha
        if voting.candidate_registrations.count() >= 15 and not voting.candidate_registrations.filter(
                pk=self.pk).exists():
            raise ValidationError("W głosowaniu nie może być więcej niż 15 kandydatów.", code='voting_candidatures_limit_reached')
        now = timezone.now()
        if now >= voting.planned_start:
            raise ValidationError("Nie można dodawać nowych kandydatur do głosowania które już się zaczęło.", code="voting_is_live")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

auditlog.register(CandidateRegistration)

class Vote(models.Model):
    """Model reprezentujący oddany głos w głosowaniu na samorząd, pola

    - candidate_registration: klucz obcy zarejestrowanego kandydata
    - microsoft_user: klucz obcy poświadczonego użytkownika aplikacji
    - created_at: Czas utworzenia obiektu (strefa UTC)

    UWAGA: Nie da się edytować obiektów
    """
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE, related_name='votes', verbose_name='kandydatura')
    microsoft_user = models.ForeignKey(AzureUser, on_delete=models.CASCADE, related_name='samorzad_votes', verbose_name='użytkownik')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='data utworzenia')

    class Meta:
        verbose_name="Głos"
        verbose_name_plural = 'Głosy'

    def parse_created_at(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        voting = self.candidate_registration.voting
        # Walidacja czasu oddanego głosu
        if timezone.now() < voting.planned_start:
            raise ValidationError("Nie można głosować przed rozpoczęciem głosowania", code='voting_not_started')
        if timezone.now() > voting.planned_end:
            raise ValidationError("Nie można głosować po zakończeniu głosowania", code='voting_gone')
        # Walidacja kandydatury
        if not self.candidate_registration.is_eligible:
            raise ValidationError("Nie można oddać głosu na kandydata, który nie został dopuszczony do wyborów.", code='illegal_candidature')
        # Walidacja ilości głosów/głosowanie i ilości głosów/kandydatura
        if Vote.objects.filter(candidate_registration=self.candidate_registration, microsoft_user=self.microsoft_user).exists():
            raise ValidationError("Już zagłosowałeś na tego kandydata.", code='vote_dupliaction')
        voting = self.candidate_registration.voting
        if Vote.objects.filter(
                candidate_registration__voting=voting,
                microsoft_user=self.microsoft_user
        ).count() == voting.votes_per_user:
            raise ValidationError("Użytkownik oddał już maksymalną ilość głosów w głosowaniu", code='vote_limit_reached')
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!", code='vote_action_forbidden')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)