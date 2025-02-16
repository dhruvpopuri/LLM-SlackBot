from django.urls import path
from .views import SlackEventsView, SlackInstallView, SlackOAuthView, ChannelSentimentAnalysisView

urlpatterns = [
    path('slack/events/', SlackEventsView.as_view(), name='slack_events'),
    path('slack/oauth/', SlackOAuthView.as_view(), name='slack_oauth'),
    path('analyze-sentiment/', ChannelSentimentAnalysisView.as_view(), name='analyze-sentiment'),
]
