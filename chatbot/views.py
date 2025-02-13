from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from .clients import GroqClient, SlackClient, FileServiceClient
from .models import Workspace, Conversation
import json
from slack_sdk import WebClient
import logging

logger = logging.getLogger(__name__)

class SlackEventsView(APIView):
    def post(self, request, *args, **kwargs):
        # Verify Slack request
        timestamp = request.headers.get('X-Slack-Request-Timestamp')
        signature = request.headers.get('X-Slack-Signature')
        
        if not SlackClient.verify_signature(
            request.body,
            timestamp,
            signature
        ):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        # Parse event data
        event_data = json.loads(request.data)

        # Handle URL verification
        if event_data.get('type') == 'url_verification':
            return Response({'challenge': event_data['challenge']})

        # Process event asynchronously
        self.process_event(event_data)
        return Response({'ok': True})

    async def process_event(self, event_data):
        try:
            event = event_data['event']
            team_id = event_data['team_id']

            # Get workspace
            workspace = await Workspace.objects.aget(slack_team_id=team_id)
            
            # Initialize services
            slack_service = SlackClient(workspace.bot_token)
            groq_service = GroqClient(workspace.groq_api_key)
            file_service = FileServiceClient()

            if event.get('type') == 'app_mention':
                await self.handle_mention(event, workspace, slack_service, groq_service)
            elif event.get('type') == 'file_shared':
                await self.handle_file(event, workspace, slack_service, groq_service, file_service)

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            raise

    async def handle_mention(self, event, workspace, slack_service, groq_service):
        # Get conversation history
        conversations = await Conversation.objects.filter(
            workspace=workspace,
            channel_id=event['channel']
        ).order_by('-created_at')[:5]

        # Prepare messages for Groq
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        for conv in reversed(conversations):
            messages.append({"role": "user", "content": conv.message})
            if conv.response:
                messages.append({"role": "assistant", "content": conv.response})
        
        messages.append({"role": "user", "content": event['text']})

        # Get response from Groq
        response = await groq_service.get_response(messages)

        # Save conversation
        await Conversation.objects.acreate(
            workspace=workspace,
            channel_id=event['channel'],
            thread_ts=event.get('thread_ts'),
            message=event['text'],
            message_type='text',
            response=response
        )

        # Send response to Slack
        await slack_service.send_message(
            channel=event['channel'],
            text=response,
            thread_ts=event.get('thread_ts')
        )

class SlackInstallView(APIView):
    def get(self, request):
        return Response({
            'url': f"https://slack.com/oauth/v2/authorize?client_id={settings.SLACK_CLIENT_ID}&scope=app_mentions:read,chat:write,files:read"
        })

class SlackOAuthView(APIView):
    async def get(self, request):
        code = request.query_params.get('code')
        if not code:
            return Response({'error': 'Missing code'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Exchange code for tokens
            client = WebClient()
            response = await client.oauth_v2_access(
                client_id=settings.SLACK_CLIENT_ID,
                client_secret=settings.SLACK_CLIENT_SECRET,
                code=code
            )

            # Store workspace credentials
            await Workspace.objects.acreate(
                slack_team_id=response['team']['id'],
                bot_token=response['access_token']
            )

            return Response({'message': 'Installation successful!'})
        except Exception as e:
            logger.error(f"OAuth error: {e}")
            return Response(
                {'error': 'OAuth failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )