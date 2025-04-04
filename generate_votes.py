import os
import random
import django
import datetime
import pytz

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ekonomvote.settings")
django.setup()

from django.db import transaction
from django.utils import timezone
from samorzad.models import Vote, CandidateRegistration

def generate_votes_with_random_dates():
    voting_id = 1
    candidate_ids = [2, 3, 4, 5, 6]
    candidate_registrations = CandidateRegistration.objects.filter(
        voting_id=voting_id,
        candidate_id__in=candidate_ids,
        is_eligible=True
    )
    registrations_map = {reg.candidate_id: reg for reg in candidate_registrations}
    for candidate_id in candidate_ids:
        if candidate_id not in registrations_map:
            print(
                f"Ostrzeżenie: Kandydat o ID {candidate_id} nie ma rejestracji dla głosowania {voting_id} lub nie jest dopuszczony")
    azure_user_ids = [f"azure_user_{i}" for i in range(1, 568)]
    weights = {
        2: 35,  # ~35% głosów
        3: 25,  # ~25% głosów
        4: 20,  # ~20% głosów
        5: 15,  # ~15% głosów
        6: 5    # ~5% głosów
    }
    weighted_candidates = []
    for candidate_id, weight in weights.items():
        if candidate_id in registrations_map:
            weighted_candidates.extend([candidate_id] * weight)
    start_time = datetime.datetime(2025, 4, 6, 9, 0, 1, tzinfo=pytz.utc)
    end_time = datetime.datetime(2025, 4, 10, 15, 59, 59, tzinfo=pytz.utc)
    time_difference_seconds = int((end_time - start_time).total_seconds())


    def random_date_between():
        random_seconds = random.randint(0, time_difference_seconds)
        return start_time + datetime.timedelta(seconds=random_seconds)
    created_votes = []
    with transaction.atomic():
        for azure_user_id in azure_user_ids:
            candidate_id = random.choice(weighted_candidates)
            registration = registrations_map[candidate_id]
            random_date = random_date_between()
            vote = Vote(
                candidate_registration=registration,
                azure_user_id=azure_user_id,
                created_at=random_date  # Ustaw losową datę utworzenia
            )
            created_votes.append(vote)
        Vote.objects.bulk_create(created_votes, ignore_conflicts=True)
    print(f"Utworzono {len(created_votes)} głosów dla głosowania {voting_id}")
    vote_counts = {}
    for vote in created_votes:
        candidate_id = vote.candidate_registration.candidate_id
        vote_counts[candidate_id] = vote_counts.get(candidate_id, 0) + 1
    print("\nRozkład głosów:")
    for candidate_id, count in vote_counts.items():
        percentage = (count / len(created_votes)) * 100
        print(f"Kandydat ID {candidate_id}: {count} głosów ({percentage:.2f}%)")
    print("\nPrzykładowe daty głosów:")
    for i, vote in enumerate(created_votes[:5]):
        print(f"Głos {i+1}: {vote.created_at}")

if __name__ == "__main__":
    generate_votes_with_random_dates()