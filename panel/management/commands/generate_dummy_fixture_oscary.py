from datetime import timedelta
import random
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from freezegun import freeze_time
import json
import uuid
from faker import Faker
import hashlib

fake = Faker('pl_PL')


def _simple_password_hash(password):
    return f"pbkdf2_sha256$600000${uuid.uuid4().hex[:22]}${hashlib.sha256(password.encode()).hexdigest()}"


def generate_azure_users(count=500):
    """Generuje użytkowników Azure AD"""
    now = timezone.now()
    c = 10
    users = []
    for i in range(count):
        microsoft_user_id = str(uuid.uuid4())
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = f"{first_name.lower()}.{last_name.lower()}{i + 1}"
        email = f"{username}@{fake.random_element(elements=('szkola.edu.pl', 'liceum.pl', 'gimnazjum.edu.pl', 'technikum.pl'))}"

        user_data = {
            "model": "office_auth.AzureUser",
            'pk': c,
            "fields": {
                "username": f'test{c}',
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "microsoft_user_id": microsoft_user_id,
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
                "password": _simple_password_hash("ZAQ!2wsx"),
            }
        }
        users.append(user_data)
        c = c + 1
    return users


def generate_oscars():
    """Generuje kategorie Oskarów"""
    oscar_categories = [
        {
            'name': 'Najlepszy Nauczyciel Roku',
            'info': 'Nagroda dla nauczyciela, który wyróżnił się wyjątkowym zaangażowaniem w proces edukacyjny, innowacyjnymi metodami nauczania i pozytywnym wpływem na rozwój uczniów.'
        },
        {
            'name': 'Mentor Młodzieży',
            'info': 'Wyróżnienie dla nauczyciela, który szczególnie wspiera uczniów w ich rozwoju osobistym i zawodowym, pełni rolę przewodnika i inspiruje do osiągania celów.'
        },
        {
            'name': 'Innowator Edukacyjny',
            'info': 'Nagroda dla nauczyciela wprowadzającego nowoczesne technologie i metody nauczania, eksperymentującego z nowymi podejściami pedagogicznymi.'
        },
        {
            'name': 'Mistrz Komunikacji',
            'info': 'Wyróżnienie dla nauczyciela, który potrafi w sposób jasny i zrozumiały przekazywać wiedzę, buduje pozytywne relacje z uczniami i rodzicami.'
        },
        {
            'name': 'Animator Społeczności Szkolnej',
            'info': 'Nagroda dla nauczyciela aktywnie organizującego wydarzenia szkolne, konkursy, wycieczki i inne inicjatywy integrujące społeczność szkolną.'
        },
        {
            'name': 'Opiekun Samorządu Uczniowskiego',
            'info': 'Wyróżnienie dla nauczyciela wspierającego działalność samorządu uczniowskiego i rozwijającego postawy obywatelskie wśród młodzieży.'
        },
        {
            'name': 'Ekspert Przedmiotowy',
            'info': 'Nagroda dla nauczyciela o głębokiej wiedzy merytorycznej, który przygotowuje uczniów do olimpiad i konkursów przedmiotowych.'
        },
        {
            'name': 'Trener Talentów',
            'info': 'Wyróżnienie dla nauczyciela odkrywającego i rozwijającego uzdolnienia uczniów, prowadzącego koła zainteresowań i zajęcia dodatkowe.'
        },
        {
            'name': 'Przyjaciel Uczniów',
            'info': 'Nagroda dla nauczyciela, który buduje przyjazną atmosferę w klasie, jest otwarty na problemy uczniów i wspiera ich w trudnych momentach.'
        },
        {
            'name': 'Promotor Kultury',
            'info': 'Wyróżnienie dla nauczyciela organizującego wydarzenia kulturalne, spektakle, wystawy i inne inicjatywy rozwijające wrażliwość artystyczną uczniów.'
        }
    ]

    oscars = []
    now = timezone.now()

    for i, category in enumerate(oscar_categories, 1):
        oscar_data = {
            'model': 'oscary.Oscar',
            'pk': i,
            'fields': {
                'name': category['name'],
                'info': category['info'],
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
            }
        }
        oscars.append(oscar_data)

    return oscars


def generate_teachers(count=80):
    """Generuje nauczycieli"""
    teachers = []
    now = timezone.now()

    # Przedmioty szkolne
    subjects = [
        'Matematyka', 'Fizyka', 'Chemia', 'Biologia', 'Geografia',
        'Historia', 'Wiedza o społeczeństwie', 'Język polski', 'Język angielski',
        'Język niemiecki', 'Język francuski', 'Informatyka', 'Plastyka',
        'Muzyka', 'Wychowanie fizyczne', 'Religia', 'Etyka', 'Filozofia',
        'Ekonomia', 'Przedsiębiorczość', 'Technika', 'Edukacja dla bezpieczeństwa'
    ]

    for i in range(count):
        first_name = fake.first_name()
        # 30% szans na drugie imię
        second_name = fake.first_name() if random.random() < 0.3 else ""
        last_name = fake.last_name()

        subject = random.choice(subjects)
        years_experience = random.randint(1, 35)

        # Generujemy różnorodne opisy nauczycieli
        info_templates = [
            f"Nauczyciel {subject.lower()} z {years_experience}-letnim stażem. Specjalizuje się w pracy z uzdolnioną młodzieżą i przygotowywaniu do olimpiad przedmiotowych.",
            f"Doświadczony pedagog uczący {subject.lower()}. Znany z innowacyjnych metod nauczania i wykorzystywania nowoczesnych technologii w edukacji.",
            f"Nauczyciel {subject.lower()}, który od {years_experience} lat inspiruje uczniów do odkrywania nowych pasji. Organizator licznych projektów edukacyjnych.",
            f"Dedykowany nauczyciel {subject.lower()} z pasją do swojego przedmiotu. Prowadzi koła zainteresowań i aktywnie uczestniczy w życiu szkoły.",
            f"Nauczyciel {subject.lower()} o szerokich zainteresowaniach. Łączy pracę dydaktyczną z działalnością wychowawczą i organizowaniem wydarzeń kulturalnych."
        ]

        teacher_data = {
            'model': 'oscary.Teacher',
            'pk': i + 1,
            'fields': {
                'first_name': first_name,
                'second_name': second_name,
                'last_name': last_name,
                'image': None,  # Można dodać ścieżki do zdjęć
                'info': random.choice(info_templates),
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
            }
        }
        teachers.append(teacher_data)

    return teachers


def generate_voting_events():
    """Generuje wydarzenia głosowania (plebiscyty)"""
    voting_events = []
    now = timezone.now()

    # Przeszłe plebiscyty
    for i in range(5):
        event_data = {
            'model': 'oscary.VotingEvent',
            'pk': i + 1,
            'fields': {
                'created_at': (now - timedelta(days=365 * (i + 1))).isoformat(),
                'updated_at': (now - timedelta(days=365 * (i + 1))).isoformat(),
                'with_nominations': random.choice([True, False]),
            }
        }
        voting_events.append(event_data)

    # Obecny plebiscyt
    current_event = {
        'model': 'oscary.VotingEvent',
        'pk': 6,
        'fields': {
            'created_at': (now - timedelta(days=30)).isoformat(),
            'updated_at': now.isoformat(),
            'with_nominations': True,
        }
    }
    voting_events.append(current_event)

    # Przyszły plebiscyt
    future_event = {
        'model': 'oscary.VotingEvent',
        'pk': 7,
        'fields': {
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'with_nominations': True,
        }
    }
    voting_events.append(future_event)

    return voting_events


def generate_voting_rounds(voting_events):
    """Generuje rundy głosowania"""
    voting_rounds = []
    now = timezone.now()
    pk_counter = 1

    for event in voting_events:
        event_id = event['pk']
        event_created = timezone.datetime.fromisoformat(event['fields']['created_at'])
        has_nominations = event['fields']['with_nominations']

        if event_id <= 5:  # Przeszłe wydarzenia
            base_date = event_created + timedelta(days=30)

            if has_nominations:
                # Runda nominacji
                nomination_round = {
                    'model': 'oscary.VotingRound',
                    'pk': pk_counter,
                    'fields': {
                        'voting_event': event_id,
                        'created_at': event_created.isoformat(),
                        'updated_at': event_created.isoformat(),
                        'planned_start': base_date.isoformat(),
                        'planned_end': (base_date + timedelta(days=7)).isoformat(),
                        'max_tearchers_for_end': random.randint(3, 5),
                        'round_type': 'N',
                    }
                }
                voting_rounds.append(nomination_round)
                pk_counter += 1

                # Runda finałowa
                final_round = {
                    'model': 'oscary.VotingRound',
                    'pk': pk_counter,
                    'fields': {
                        'voting_event': event_id,
                        'created_at': event_created.isoformat(),
                        'updated_at': event_created.isoformat(),
                        'planned_start': (base_date + timedelta(days=14)).isoformat(),
                        'planned_end': (base_date + timedelta(days=21)).isoformat(),
                        'max_tearchers_for_end': 1,
                        'round_type': 'F',
                    }
                }
                voting_rounds.append(final_round)
                pk_counter += 1
            else:
                # Tylko runda finałowa
                final_round = {
                    'model': 'oscary.VotingRound',
                    'pk': pk_counter,
                    'fields': {
                        'voting_event': event_id,
                        'created_at': event_created.isoformat(),
                        'updated_at': event_created.isoformat(),
                        'planned_start': base_date.isoformat(),
                        'planned_end': (base_date + timedelta(days=14)).isoformat(),
                        'max_tearchers_for_end': 1,
                        'round_type': 'F',
                    }
                }
                voting_rounds.append(final_round)
                pk_counter += 1

        elif event_id == 6:  # Obecne wydarzenie
            # Runda nominacji (zakończona)
            nomination_round = {
                'model': 'oscary.VotingRound',
                'pk': pk_counter,
                'fields': {
                    'voting_event': event_id,
                    'created_at': event_created.isoformat(),
                    'updated_at': event_created.isoformat(),
                    'planned_start': (now - timedelta(days=21)).isoformat(),
                    'planned_end': (now - timedelta(days=14)).isoformat(),
                    'max_tearchers_for_end': 3,
                    'round_type': 'N',
                }
            }
            voting_rounds.append(nomination_round)
            pk_counter += 1

            # Runda finałowa (trwająca)
            final_round = {
                'model': 'oscary.VotingRound',
                'pk': pk_counter,
                'fields': {
                    'voting_event': event_id,
                    'created_at': event_created.isoformat(),
                    'updated_at': event_created.isoformat(),
                    'planned_start': (now - timedelta(days=2)).isoformat(),
                    'planned_end': (now + timedelta(days=5)).isoformat(),
                    'max_tearchers_for_end': 1,
                    'round_type': 'F',
                }
            }
            voting_rounds.append(final_round)
            pk_counter += 1

        else:  # Przyszłe wydarzenie
            # Runda nominacji (przyszła)
            nomination_round = {
                'model': 'oscary.VotingRound',
                'pk': pk_counter,
                'fields': {
                    'voting_event': event_id,
                    'created_at': event_created.isoformat(),
                    'updated_at': event_created.isoformat(),
                    'planned_start': (now + timedelta(days=30)).isoformat(),
                    'planned_end': (now + timedelta(days=37)).isoformat(),
                    'max_tearchers_for_end': 3,
                    'round_type': 'N',
                }
            }
            voting_rounds.append(nomination_round)
            pk_counter += 1

            # Runda finałowa (przyszła)
            final_round = {
                'model': 'oscary.VotingRound',
                'pk': pk_counter,
                'fields': {
                    'voting_event': event_id,
                    'created_at': event_created.isoformat(),
                    'updated_at': event_created.isoformat(),
                    'planned_start': (now + timedelta(days=44)).isoformat(),
                    'planned_end': (now + timedelta(days=51)).isoformat(),
                    'max_tearchers_for_end': 1,
                    'round_type': 'F',
                }
            }
            voting_rounds.append(final_round)
            pk_counter += 1

    return voting_rounds


def generate_candidatures(voting_rounds, oscars, teachers):
    """Generuje kandydatury (teacher-oscar-voting_round)"""
    candidatures = []
    now = timezone.now()
    pk_counter = 1

    oscar_count = len(oscars)
    teacher_count = len(teachers)

    for voting_round in voting_rounds:
        round_id = voting_round['pk']

        # Dla każdego oskara w każdej rundzie
        for oscar in oscars:
            oscar_id = oscar['pk']

            # Losowa liczba kandydatów na oskara (3-8)
            num_candidates = random.randint(3, 8)

            # Losowo wybieramy nauczycieli
            selected_teachers = random.sample(range(1, teacher_count + 1),
                                              min(num_candidates, teacher_count))

            for teacher_id in selected_teachers:
                candidature_data = {
                    'model': 'oscary.Candidature',
                    'pk': pk_counter,
                    'fields': {
                        'oscar': oscar_id,
                        'teacher': teacher_id,
                        'voting_round': round_id,
                        'created_at': now.isoformat(),
                    }
                }
                candidatures.append(candidature_data)
                pk_counter += 1

    return candidatures


def generate_votes(candidatures, voting_rounds, users):
    """Generuje głosy użytkowników"""
    votes = []
    pk_counter = 1
    now = timezone.now()

    # Grupujemy kandydatury po rundach
    candidatures_by_round = {}
    for candidature in candidatures:
        round_id = candidature['fields']['voting_round']
        if round_id not in candidatures_by_round:
            candidatures_by_round[round_id] = []
        candidatures_by_round[round_id].append(candidature)

    for voting_round in voting_rounds:
        round_id = voting_round['pk']
        planned_start = timezone.datetime.fromisoformat(voting_round['fields']['planned_start'])
        planned_end = timezone.datetime.fromisoformat(voting_round['fields']['planned_end'])

        # Sprawdzamy czy runda się już rozpoczęła
        if planned_start > now:
            continue

        # Sprawdzamy czy runda już się zakończyła
        if planned_end < now:
            voting_end_time = planned_end
        else:
            voting_end_time = now

        total_seconds = int((voting_end_time - planned_start).total_seconds())
        if total_seconds <= 0:
            continue

        round_candidatures = candidatures_by_round.get(round_id, [])
        if not round_candidatures:
            continue

        # Grupujemy kandydatury po oskarach (jeden głos na oskara)
        candidatures_by_oscar = {}
        for candidature in round_candidatures:
            oscar_id = candidature['fields']['oscar']
            if oscar_id not in candidatures_by_oscar:
                candidatures_by_oscar[oscar_id] = []
            candidatures_by_oscar[oscar_id].append(candidature)

        # Symulujemy głosowanie użytkowników
        # Im nowsza runda, tym większy udział (od 60% do 85%)
        participation_rate = random.uniform(0.6, 0.85)
        voting_users = random.sample(users, int(len(users) * participation_rate))

        for user in voting_users:
            user_id = user['pk']

            # Użytkownik głosuje na każdy oskar (może nie na wszystkie)
            for oscar_id, oscar_candidatures in candidatures_by_oscar.items():
                # 90% szans na oddanie głosu na konkretny oskar
                if random.random() < 0.9:
                    # Wybieramy jedną kandydaturę z tego oskara
                    selected_candidature = random.choice(oscar_candidatures)

                    # Losowy moment głosowania w trakcie rundy
                    random_seconds = random.randint(0, total_seconds)
                    vote_time = planned_start + timedelta(seconds=random_seconds)

                    vote_data = {
                        'model': 'oscary.Vote',
                        'pk': pk_counter,
                        'fields': {
                            'candidature': selected_candidature['pk'],
                            'microsoft_user': user_id,
                            'created_at': vote_time.isoformat(),
                        }
                    }
                    votes.append(vote_data)
                    pk_counter += 1

    return votes


class Command(BaseCommand):
    help = "Tworzy fixturę z fałszywymi danymi dla systemu Oskarów. Po wygenerowaniu fixtury należy ją załadować do bazy danych za pomocą python manage.py loaddata"

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='oscar_dummy_fixture.json', help='Nazwa pliku wyjściowego')
        parser.add_argument('--users', type=int, default=500, help='Liczba użytkowników do wygenerowania')
        parser.add_argument('--teachers', type=int, default=80, help='Liczba nauczycieli do wygenerowania')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Generowanie fixtury dla systemu Oskarów...'))

        # Generujemy wszystkie dane
        fixture_data = []

        # Użytkownicy Azure AD
        self.stdout.write('Generowanie użytkowników Azure AD...')
        users = generate_azure_users(options['users'])
        fixture_data.extend(users)

        # Kategorie Oskarów
        self.stdout.write('Generowanie kategorii Oskarów...')
        oscars = generate_oscars()
        fixture_data.extend(oscars)

        # Nauczyciele
        self.stdout.write('Generowanie nauczycieli...')
        teachers = generate_teachers(options['teachers'])
        fixture_data.extend(teachers)

        # Wydarzenia głosowania
        self.stdout.write('Generowanie wydarzeń głosowania...')
        voting_events = generate_voting_events()
        fixture_data.extend(voting_events)

        # Rundy głosowania
        self.stdout.write('Generowanie rund głosowania...')
        voting_rounds = generate_voting_rounds(voting_events)
        fixture_data.extend(voting_rounds)

        # Kandydatury
        self.stdout.write('Generowanie kandydatur...')
        candidatures = generate_candidatures(voting_rounds, oscars, teachers)
        fixture_data.extend(candidatures)

        # Głosy
        self.stdout.write('Generowanie głosów...')
        votes = generate_votes(candidatures, voting_rounds, users)
        fixture_data.extend(votes)

        # Zapisujemy do pliku
        output_file = options['output']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(fixture_data, f, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f'Fixtura dla systemu Oskarów została wygenerowana pomyślnie!\n'
                f'Plik: {output_file}\n'
                f'Użytkownicy: {options["users"]}\n'
                f'Nauczyciele: {options["teachers"]}\n'
                f'Kategorie Oskarów: {len(oscars)}\n'
                f'Wydarzenia głosowania: {len(voting_events)}\n'
                f'Rundy głosowania: {len(voting_rounds)}\n'
                f'Kandydatury: {len(candidatures)}\n'
                f'Głosy: {len(votes)}\n'
                f'Łączna liczba obiektów: {len(fixture_data)}'
            )
        )