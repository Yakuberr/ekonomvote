from django.db import transaction
from django.http import HttpRequest
from django.contrib.contenttypes.models import ContentType

from oscary.models import VotingEvent, VotingRound
from office_auth.models import ActionLog

def create_event_voting_db_helper(cleaned_data:dict, request:HttpRequest):
    """Helper który tworzy wydarzenie głosowania i jego rundy
    na bazie danych z formularza. Używany w panel.views.oscary.create_voting_event"""
    with transaction.atomic():
        with_nominations = cleaned_data.get('with_nominations')
        voting_event = VotingEvent.objects.create(
            with_nominations=with_nominations
        )
        ActionLog.objects.create(
            user=request.user,
            action_type=ActionLog.ActionType.CREATE,
            altered_fields={},
            content_type=ContentType.objects.get_for_model(VotingEvent),
            object_id=voting_event.id,
        )
        final_round = VotingRound.objects.create(
            planned_start=cleaned_data.get('l_round_start'),
            planned_end=cleaned_data.get('l_round_end'),
            voting_event=voting_event,
            round_type=VotingRound.VotingRoundType.FINAL
        )
        ActionLog.objects.create(
            user=request.user,
            action_type=ActionLog.ActionType.CREATE,
            altered_fields={},
            content_type=ContentType.objects.get_for_model(VotingRound),
            object_id=final_round.id,
        )
        if with_nominations:
            nomination_round = VotingRound.objects.create(
                planned_start=cleaned_data.get('f_round_start'),
                planned_end=cleaned_data.get('f_round_end'),
                voting_event=voting_event,
                round_type=VotingRound.VotingRoundType.NOMINATION,
                max_tearchers_for_end=cleaned_data.get('f_round_t_count')
            )
            ActionLog.objects.create(
                user=request.user,
                action_type=ActionLog.ActionType.CREATE,
                altered_fields={},
                content_type=ContentType.objects.get_for_model(VotingRound),
                object_id=nomination_round.id,
            )
    return voting_event


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