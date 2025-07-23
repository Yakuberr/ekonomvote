from django.contrib import admin

from .models import Teacher, Candidature, Oscar, Vote, VotingEvent, VotingRound

admin.site.register(Candidature)
admin.site.register(Teacher)
admin.site.register(Oscar)
admin.site.register(Vote)
admin.site.register(VotingEvent)
admin.site.register(VotingRound)


# Register your models here.
