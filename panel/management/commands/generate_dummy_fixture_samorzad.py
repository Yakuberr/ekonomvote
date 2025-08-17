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


def generate_azure_users(count=800):
    now = timezone.now()
    c = 10
    users = []
    for i in range(count):
        # Generowanie unikalnego Microsoft User ID (podobnego do rzeczywistego Azure AD)
        microsoft_user_id = str(uuid.uuid4())
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = f"{first_name.lower()}.{last_name.lower()}{i + 1}"
        email = f"{username}@{fake.random_element(elements=('company.com', 'firma.pl', 'example.org', 'test.com'))}"
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


def generate_votings():
    votings = []
    now = timezone.now()
    # Przeszłe głosowania
    for i in range(15):
        voting_data = {
            'model': 'samorzad.Voting',
            'pk': i + 1,
            'fields': {
                'planned_start': (now - timedelta(days=i + 2)).isoformat(),
                'planned_end': (now - timedelta(days=i + 1)).isoformat(),
                'votes_per_user': random.choices([2, 3, 4], weights=[0.1, 0.85, 0.05])[0],
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
            }
        }
        votings.append(voting_data)

    # Przyszłe głosowania
    for i in range(4):
        voting_data = {
            'model': 'samorzad.Voting',
            'pk': i + 16,
            'fields': {
                'planned_start': (now + timedelta(days=i + 12)).isoformat(),
                'planned_end': (now + timedelta(days=i + 13)).isoformat(),
                'votes_per_user': random.choices([2, 3, 4], weights=[0.1, 0.85, 0.05])[0],
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
            }
        }
        votings.append(voting_data)

    # Obecne głosowanie (zaczęło się wcześniej, kończy się za 3 dni)
    current_voting = {
        'model': 'samorzad.Voting',
        'pk': 20,
        'fields': {
            'planned_start': (now - timedelta(days=1)).isoformat(),
            'planned_end': (now + timedelta(days=3)).isoformat(),
            'votes_per_user': 3,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
        }
    }
    votings.append(current_voting)

    return votings


def generate_candidates(count=50):
    candidates = []
    school_classes = [
        '1A', '1B', '1C', '1D', '1E',
        '2A', '2B', '2C', '2D', '2E',
        '3A', '3B', '3C', '3D', '3E',
        '4A', '4B', '4C', '4D', '4E'
    ]
    now = timezone.now()
    for i in range(count):
        # Czasami dodajemy drugie imię
        second_name = fake.first_name() if random.random() < 0.3 else ""

        candidate_data = {
            'model': 'samorzad.Candidate',
            'pk': i + 1,
            'fields': {
                'first_name': fake.first_name(),
                'second_name': second_name,
                'last_name': fake.last_name(),
                'image': None,  # Możesz dodać ścieżki do obrazów jeśli masz
                'school_class': random.choice(school_classes),
                'created_at': now.isoformat(),
                'updated_at': now.isoformat(),
            }
        }
        candidates.append(candidate_data)

    return candidates


def generate_candidate_registrations():
    registrations = []
    pk_counter = 1
    now = timezone.now()
    # Dla każdego głosowania generujemy kandydatury
    for voting_id in range(1, 21):  # 20 głosowań
        # Losowa liczba kandydatów dla każdego głosowania (5-15)
        num_candidates = random.randint(5, 15)

        # Losowo wybieramy kandydatów
        selected_candidates = random.sample(range(1, 51), num_candidates)  # 50 kandydatów

        for candidate_id in selected_candidates:
            # 95% szans na dopuszczenie do wyborów
            is_eligible = random.random() < 0.95

            registration_data = {
                'model': 'samorzad.CandidateRegistration',
                'pk': pk_counter,
                'fields': {
                    'candidate': candidate_id,
                    'voting': voting_id,
                    'is_eligible': is_eligible,
                    'created_at': now.isoformat(),
                    'updated_at': now.isoformat(),
                }
            }
            registrations.append(registration_data)
            pk_counter += 1

    return registrations


def generate_electoral_programs(registrations:list):
    programs = []
    now = timezone.now()
    # Szablony programów wyborczych w HTML
    program_templates = [
        """
        <div class="electoral-program">
            <h2>Mój program wyborczy</h2>
            <h3>🎯 Główne cele:</h3>
            <ul>
                <li><strong>Poprawa warunków nauki</strong> - modernizacja sal lekcyjnych</li>
                <li><strong>Więcej wydarzeń kulturalnych</strong> - organizacja konkursów i festiwali</li>
                <li><strong>Lepsze wyżywienie</strong> - rozszerzenie menu w stołówce</li>
            </ul>
            <h3>📚 Edukacja:</h3>
            <p>Będę zabiegać o wprowadzenie nowoczesnych technologii do procesu nauczania oraz organizację dodatkowych zajęć pozalekcyjnych.</p>
            <h3>🤝 Społeczność:</h3>
            <p>Chcę wzmocnić więzi między uczniami poprzez organizację więcej wydarzeń integracyjnych i projektów współpracy.</p>
        </div>
        """,
        """
        <div class="electoral-program">
            <h2>Program na rzecz uczniów</h2>
            <div class="priority-section">
                <h3>🏆 Priorytet #1: Sport i rekreacja</h3>
                <p>Organizacja turniejów międzyklasowych i poprawa bazy sportowej.</p>
            </div>
            <div class="priority-section">
                <h3>🎨 Priorytet #2: Rozwijanie talentów</h3>
                <p>Utworzenie klubów zainteresowań i wsparcie dla uzdolnionych uczniów.</p>
            </div>
            <div class="priority-section">
                <h3>🌍 Priorytet #3: Ekologia</h3>
                <p>Wprowadzenie programów ekologicznych i segregacji odpadów w szkole.</p>
            </div>
            <blockquote>
                <p>"Razem możemy zmienić naszą szkołę na lepsze!"</p>
            </blockquote>
        </div>
        """,
        """
        <div class="electoral-program">
            <h2>Innowacyjne rozwiązania dla szkoły</h2>
            <div class="modern-section">
                <h3>💡 Digitalizacja:</h3>
                <p>Wprowadzenie aplikacji mobilnej dla uczniów z planem lekcji i ocenami.</p>
            </div>
            <div class="modern-section">
                <h3>🗣️ Komunikacja:</h3>
                <p>Regularne spotkania z samorządem i system zgłaszania problemów.</p>
            </div>
            <div class="modern-section">
                <h3>🎪 Rozrywka:</h3>
                <p>Organizacja dni tematycznych, dyskotek i wycieczek klasowych.</p>
            </div>
            <hr>
            <p><em>Głosując na mnie, głosujesz na przyszłość naszej szkoły!</em></p>
        </div>
        """,
        """
        <div class="electoral-program">
            <h2>Razem dla lepszej szkoły</h2>
            <table style="width: 100%; border-collapse: collapse;">
                <tr style="background-color: #f0f0f0;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Obszar</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Propozycje</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Infrastruktura</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">Nowe ławki, tablice interaktywne</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Kultura</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">Teatr szkolny, zespoły muzyczne</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Sport</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">Liga szkolna, dni sportowe</td>
                </tr>
            </table>
            <h3>🤝 Moje zobowiązania:</h3>
            <ol>
                <li>Transparentność w działaniach samorządu</li>
                <li>Regularne konsultacje z uczniami</li>
                <li>Realizacja obietnic wyborczych</li>
            </ol>
        </div>
        """
    ]

    # Generujemy programy dla kandydatur, które są dopuszczone do wyborów
    pk_counter = 1
    for registration in registrations:
            program_data = {
                'model': 'samorzad.ElectoralProgram',
                'pk': pk_counter,
                'fields': {
                    'candidature': registration['pk'],
                    'info': random.choice(program_templates).strip(),
                    'created_at': now.isoformat(),
                    'updated_at': now.isoformat(),
                }
            }
            programs.append(program_data)
            pk_counter += 1

    return programs


def generate_votes(registrations, users, votings):
    votes = []
    pk_counter = 1

    for voting in votings:
        voting_id = voting['pk']
        votes_per_user = voting['fields']['votes_per_user']

        planned_start = timezone.datetime.fromisoformat(voting['fields']['planned_start'])
        planned_end = timezone.datetime.fromisoformat(voting['fields']['planned_end'])

        total_seconds = int((timezone.now() - planned_start).total_seconds())
        if total_seconds < 0:
            continue

        # Pobierz kandydatury dopuszczone do tego głosowania
        eligible_registrations = [
            reg for reg in registrations
            if reg['fields']['voting'] == voting_id and reg['fields']['is_eligible']
        ]

        if not eligible_registrations:
            continue

        # Symulujemy głosy użytkowników
        voting_users = users

        for user in voting_users:
            user_id = user['pk']

            # Losowo ustalamy ile głosów odda ten użytkownik (nie więcej niż votes_per_user)
            votes_to_cast = random.randint(1, votes_per_user)
            if votes_to_cast > len(eligible_registrations):
                votes_to_cast = len(eligible_registrations)

            selected_candidates = random.sample(eligible_registrations, votes_to_cast)

            for reg in selected_candidates:
                random_seconds = random.randint(0, total_seconds)
                created_date = planned_start + timedelta(seconds=random_seconds)

                vote_data = {
                    'model': 'samorzad.Vote',
                    'pk': pk_counter,
                    'fields': {
                        'candidate_registration': reg['pk'],
                        'microsoft_user': user_id,
                        'created_at': created_date.isoformat(),
                    }
                }
                votes.append(vote_data)
                pk_counter += 1

    return votes


class Command(BaseCommand):
    help = "Tworzy fixturę z fałszywymi danymi dla celów testowych. Po wygenerowaniu fixtury należy ją załadować do bazy danych za pomocą python manage.py loaddata"

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='samorzad_dummy_fixture.json', help='Nazwa pliku wyjściowego')
        parser.add_argument('--users', type=int, default=800, help='Liczba użytkowników do wygenerowania')
        parser.add_argument('--candidates', type=int, default=50, help='Liczba kandydatów do wygenerowania')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Generowanie fixtury...'))

        # Generujemy wszystkie dane
        fixture_data = []

        # Użytkownicy
        self.stdout.write('Generowanie użytkowników...')
        users = generate_azure_users(options['users'])
        fixture_data.extend(users)

        # Głosowania
        self.stdout.write('Generowanie głosowań...')
        votings = generate_votings()
        fixture_data.extend(votings)

        # Kandydaci
        self.stdout.write('Generowanie kandydatów...')
        candidates = generate_candidates(options['candidates'])
        fixture_data.extend(candidates)

        # Kandydatury
        self.stdout.write('Generowanie kandydatur...')
        registrations = generate_candidate_registrations()
        fixture_data.extend(registrations)

        # Programy wyborcze
        self.stdout.write('Generowanie programów wyborczych...')
        fixture_data.extend(generate_electoral_programs(registrations=registrations))

        # Głosy
        self.stdout.write('Generowanie głosów...')
        fixture_data.extend(generate_votes(
            registrations=registrations,
            users=users,
            votings=votings
        ))

        # Zapisujemy do pliku
        output_file = options['output']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(fixture_data, f, ensure_ascii=False, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f'Fixtura została wygenerowana pomyślnie!\n'
                f'Plik: {output_file}\n'
                f'Użytkownicy: {options["users"]}\n'
                f'Kandydaci: {options["candidates"]}\n'
                f'Głosowania: 20 (w tym 1 obecne)\n'
                f'Kandydatury: {len(registrations)}\n'
                f'Łączna liczba obiektów: {len(fixture_data)}'
            )
        )
