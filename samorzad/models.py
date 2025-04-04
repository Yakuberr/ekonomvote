from django.db import models
from django.utils import timezone, dateparse
from django.core.exceptions import ValidationError
import pytz

class Voting(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    planned_start = models.DateTimeField(null=False, unique=True)
    planned_end = models.DateTimeField(null=False, unique=True)

    def parse_planned_start(self):
        return self.planned_start.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def parse_planned_end(self):
        return self.planned_end.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        if self.planned_start <= timezone.now():
            raise ValidationError("planned_start musi być większe niż obecna data i godzina.")
        if self.planned_start >= self.planned_end:
            raise ValidationError("planned_start musi być mniejsze niż planned_end.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Voting(start={self.parse_planned_start()}, end={self.parse_planned_end()})'

class Candidate(models.Model):
    first_name = models.CharField(null=False, max_length=150)
    second_name = models.CharField(null=True, blank=True, max_length=150)
    last_name = models.CharField(null=False, max_length=150)
    image = models.ImageField(upload_to='uploads/samorzad/', null=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_eligible = models.BooleanField(default=False)

    def __str__(self):
        return f'Candiate(first_name={self.first_name}, last_name={self.last_name})'

class ElectoralProgram(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='electoral_programs', null=False)
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='electoral_programs', null=False)
    info = models.TextField(null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_program_per_voting_per_candidate')
        ]

    def __str__(self):
        return f'ElectoralProgram(candidate={self.candidate.pk}, voting={self.voting.pk})'


class CandidateRegistration(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='registrations')
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='candidate_registrations')
    is_eligible = models.BooleanField(default=False)  # Przeniesione z modelu Candidate
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'voting'], name='unique_candidate_per_voting')
        ]

    def __str__(self):
        return f'CandidateRegistration(candidate={self.candidate.pk}, voting={self.voting.pk})'


class Vote(models.Model):
    candidate_registration = models.ForeignKey(CandidateRegistration, on_delete=models.CASCADE, related_name='votes')
    azure_user_id = models.CharField(null=False, max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def parse_planned_end(self):
        return self.created_at.astimezone(tz=pytz.timezone('Europe/Warsaw')).strftime('%Y.%m.%d %H:%M:%S')

    def clean(self):
        voting = self.candidate_registration.voting
        # if timezone.now() < voting.planned_start:
        #     raise ValidationError("Nie można głosować przed rozpoczęciem głosowania")
        # if timezone.now() > voting.planned_end:
        #     raise ValidationError("Nie można głosować po zakończeniu głosowania")
        if not self.candidate_registration.is_eligible:
            raise ValidationError("Nie można oddać głosu na kandydata, który nie został dopuszczony do wyborów.")

    def save(self, *args, **kwargs):
        # Sprawdzamy unikalność głosu dla danego użytkownika w danym głosowaniu
        voting = self.candidate_registration.voting
        if Vote.objects.filter(
                candidate_registration__voting=voting,
                azure_user_id=self.azure_user_id
        ).exists():
            raise ValidationError("Użytkownik już oddał głos w tym głosowaniu")

        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!")

        self.full_clean()
        super().save(*args, **kwargs)