# Generated by Django 4.2.1 on 2025-04-02 07:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('samorzad', '0003_remove_candidate_winner_candidate_is_eligible'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='candidate',
            name='info',
        ),
        migrations.CreateModel(
            name='ElectoralProgram',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('info', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('candidate', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='electoral_programs', to='samorzad.candidate')),
                ('voting', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='electoral_programs', to='samorzad.voting')),
            ],
        ),
        migrations.AddConstraint(
            model_name='electoralprogram',
            constraint=models.UniqueConstraint(fields=('candidate', 'voting'), name='unique_program_per_voting_per_candidate'),
        ),
    ]
