# Generated by Django 5.0.2 on 2025-02-13 18:24

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SlackWorkspace',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('team_id', models.CharField(max_length=32, unique=True)),
                ('team_name', models.CharField(max_length=255)),
                ('bot_user_id', models.CharField(max_length=32)),
                ('bot_token', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ConversationHistory',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('channel_id', models.CharField(max_length=32)),
                ('thread_ts', models.CharField(max_length=32, null=True)),
                ('message_ts', models.CharField(max_length=32)),
                ('user_id', models.CharField(max_length=32)),
                ('message_text', models.TextField()),
                ('is_bot_message', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='chatbot.slackworkspace')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
