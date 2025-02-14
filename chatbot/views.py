from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings, time
from .clients import GroqClient, SlackClient, FileServiceClient
from .models import SlackWorkspace, ConversationHistory
from slack_sdk import WebClient
from rest_framework.renderers import JSONRenderer
import logging

logger = logging.getLogger(__name__)


class SlackEventsView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        timestamp = request.headers.get('X-Slack-Request-Timestamp')
        signature = request.headers.get('X-Slack-Signature')

        event_data = request.data
        if event_data.get('type') == 'url_verification':
            return Response({'challenge': event_data['challenge']})
        print(timestamp, signature)

        # Process event asynchronously
        self.process_event(event_data)
        return Response({'ok': True})

    def process_event(self, event_data):
        try:
            event = event_data['event']
            team_id = event_data['team_id']

            # Get workspace
            workspace = SlackWorkspace.objects.get(team_id=team_id)

            # Initialize services
            slack_service = SlackClient(workspace.bot_token)
            groq_service = GroqClient()

            if event.get('type') == 'app_mention':
                self.handle_mention(event, workspace, slack_service,
                                    groq_service)

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            raise

    def handle_mention(self, event, workspace, slack_service, groq_service):
        # Get conversation history
        conversations = ConversationHistory.objects.filter(
            workspace=workspace,
            channel_id=event['channel']).order_by('-created_at')[:5]

        # Prepare messages for Groq
        messages = [{
            "role": "system",
            "content": "You are a helpful assistant."
        }]
        for conv in reversed(conversations):
            messages.append({"role": "user", "content": conv.message_text})
            if conv.response:
                messages.append({
                    "role": "assistant",
                    "content": conv.response
                })

        messages.append({"role": "user", "content": event['text']})

        response = groq_service.get_response(messages)

        # Save conversation
        print(f"Event is {event}")
        ConversationHistory.objects.create(workspace=workspace,
                                           channel_id=event['channel'],
                                           thread_ts=event.get('thread_ts'),
                                           message_text=event['text'],
                                           message_ts='text',
                                           response=response)

        # Send response to Slack
        slack_service.send_message(channel=event['channel'],
                                   text=response,
                                   thread_ts=event.get('thread_ts'))


class SlackInstallView(APIView):

    def get(self, request):
        return Response({
            'url':
            f"https://slack.com/oauth/v2/authorize?client_id={settings.SLACK_CLIENT_ID}&scope=app_mentions:read,chat:write,files:read"
        })


class SlackOAuthView(APIView):
    renderer_classes = [JSONRenderer]

    def get(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({'error': 'Missing code'},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            # Exchange code for tokens
            client = WebClient()
            response = client.oauth_v2_access(
                client_id=settings.SLACK_CLIENT_ID,
                client_secret=settings.SLACK_CLIENT_SECRET,
                code=code)

            # Store workspace credentials
            SlackWorkspace.objects.update_or_create(
                team_id=response['team']['id'],
                bot_token=response['access_token'],
                team_name=response['team']['name'],
                bot_user_id=response['bot_user_id'])

            return Response({'message': 'Installation successful!'})
        except Exception as e:
            logger.error(f"OAuth error: {e}")
            return Response({'error': 'OAuth failed'},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
