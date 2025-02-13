from django.db import models
import uuid


class BaseModel(models.Model):
    uuid = models.UUIDField(primary_key=True,
                            default=uuid.uuid4,
                            editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SlackWorkspace(BaseModel):
    team_id = models.CharField(max_length=32, unique=True)
    team_name = models.CharField(max_length=255)
    bot_user_id = models.CharField(max_length=32)
    bot_token = models.CharField(max_length=255)


class ConversationHistory(BaseModel):
    workspace = models.ForeignKey(SlackWorkspace, on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=32)
    thread_ts = models.CharField(max_length=32, null=True)
    message_ts = models.CharField(max_length=32)
    user_id = models.CharField(max_length=32)
    message_text = models.TextField()
    is_bot_message = models.BooleanField(default=False)
    response = models.TextField(default="")
