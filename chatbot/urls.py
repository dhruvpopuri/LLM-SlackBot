from django.urls import path
from .views import (
    SlackEventsView,
    SlackOAuthView,
)

urlpatterns = [
    path('slack/events/', SlackEventsView.as_view(), name='slack_events'),
    path('slack/oauth/', SlackOAuthView.as_view(), name='slack_oauth'),
]
