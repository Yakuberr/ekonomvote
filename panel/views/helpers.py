from datetime import datetime

from django.db import transaction
from django.http import HttpRequest
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case, When, Value, CharField, OuterRef, Subquery, DateTimeField, IntegerField

from oscary.models import VotingEvent, VotingRound
from office_auth.models import ActionLog

class OscarHelpers:

    @staticmethod
    def create_event_voting_db_helper(cleaned_data:dict, request:HttpRequest):
        """Helper który tworzy wydarzenie głosowania i jego rundy
        na bazie danych z formularza. Używany w panel.views.oscary.create_voting_event"""
        with transaction.atomic():
            with_nominations = cleaned_data.get('with_nominations')
            voting_event = VotingEvent.objects.create(
                with_nominations=with_nominations
            )
            final_round = VotingRound.objects.create(
                planned_start=cleaned_data.get('l_round_start'),
                planned_end=cleaned_data.get('l_round_end'),
                voting_event=voting_event,
                round_type=VotingRound.VotingRoundType.FINAL
            )
            if with_nominations:
                nomination_round = VotingRound.objects.create(
                    planned_start=cleaned_data.get('f_round_start'),
                    planned_end=cleaned_data.get('f_round_end'),
                    voting_event=voting_event,
                    round_type=VotingRound.VotingRoundType.NOMINATION,
                    max_tearchers_for_end=cleaned_data.get('f_round_t_count')
                )
        first_round = nomination_round if with_nominations else final_round
        voting_event.populate_first_round(first_round=first_round)
        return voting_event

    @staticmethod
    def update_event_voting_db_helper(cleaned_data:dict, voting_event_id:int, voting_nomination_id:int|None, voting_final_id:int, with_nominations:bool):
        """Helper który tworzy wydarzenie głosowania i jego rundy
        na bazie danych z formularza. Używany w panel.views.oscary.create_voting_event"""
        with transaction.atomic():
            voting_event = VotingEvent.objects.filter(id=voting_event_id).first()
            final_round = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.FINAL, id=voting_final_id).first()
            final_round.planned_start=cleaned_data.get('l_round_start')
            final_round.planned_end=cleaned_data.get('l_round_end')
            final_round.save()
            if with_nominations:
                nomination_round = VotingRound.objects.filter(round_type=VotingRound.VotingRoundType.NOMINATION, id=voting_nomination_id).first()
                nomination_round.planned_start = cleaned_data.get('f_round_start')
                nomination_round.planned_end = cleaned_data.get('f_round_end')
                nomination_round.max_tearchers_for_end = cleaned_data.get('f_round_t_count')
                nomination_round.save()
        return voting_event


    @staticmethod
    def partial_list_voting_events_db_helper(sort_data:dict, filter_data:dict, page_number:int, now:datetime):
        voting_events = VotingEvent.objects.prefetch_related('voting_rounds')
        first_round_start = VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_start').values('planned_start')[:1]
        first_round_end = VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('planned_end').values('planned_end')[:1]
        last_round_start = VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('-planned_start').values('planned_start')[:1]
        last_round_end = VotingRound.objects.filter(
            voting_event=OuterRef('pk')
        ).order_by('-planned_end').values('planned_end')[:1]
        teachers_per_end = VotingRound.objects.filter(voting_event=OuterRef('pk')).order_by('planned_start').values(
            'max_tearchers_for_end')[:1]
        voting_events = VotingEvent.objects.annotate(
            first_round_start=Case(
                When(with_nominations=True, then=Subquery(first_round_start, output_field=DateTimeField())),
                default=Value(None),
                output_field=DateTimeField(),
            ),
            first_round_end=Case(
                When(with_nominations=True, then=Subquery(first_round_end, output_field=DateTimeField())),
                default=Value(None),
                output_field=DateTimeField(),
            ),
            last_round_start=Subquery(last_round_start, output_field=DateTimeField(), ),
            last_round_end=Subquery(last_round_end, output_field=DateTimeField(), ),
        ).annotate(teachers_per_end=Subquery(teachers_per_end, output_field=IntegerField(), ))
        voting_events = voting_events.order_by(*sort_data['sort_fields'])
        if len(filter_data) != 0:
            voting_events = voting_events.filter(**filter_data)
        return voting_events