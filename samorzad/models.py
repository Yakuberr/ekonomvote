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
        # na czas testowania zakomentowane
        # if self.planned_start <= timezone.now():
        #     raise ValidationError("planned_start musi być większe niż obecna data i godzina.")
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

class Vote(models.Model):
    voting = models.ForeignKey(Voting, on_delete=models.CASCADE, related_name='votes', null=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='votes', null=False)
    azure_user_id = models.CharField(null=False, max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['voting', 'azure_user_id'], name='unique_user_vote_per_voting')
        ]

    def __str__(self):
        return f'Vote(azure_user={self.azure_user_id}, candidate={self.candidate.pk}, voting={self.voting.pk})'

    def clean(self):
        if timezone.now() < self.voting.planned_start:
            raise ValidationError("Nie można głosować przed rozpoczęciem głosowania")
        if timezone.now() > self.voting.planned_end:
            raise ValidationError("Nie można głosować po zakończeniu głosowania")
        if not self.candidate.is_eligible:
            raise ValidationError("Nie można oddać głosu na kandydata, który nie został dopuszczony do wyborów.")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Edytowanie modelu Vote jest zabronione!")
        self.full_clean()
        super().save(*args, **kwargs)