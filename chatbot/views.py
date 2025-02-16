from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings, time
from .clients import GroqClient, SlackClient
from .models import SlackWorkspace, ConversationHistory, ChannelAnalysis
from slack_sdk import WebClient
from rest_framework.renderers import JSONRenderer
import logging
from .tasks import analyze_channel_sentiment

logger = logging.getLogger(__name__)


class SlackEventsView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        try:
            # Get request data
            event_data = request.data

            # Verify Slack request signature
            timestamp = request.headers.get('X-Slack-Request-Timestamp')
            signature = request.headers.get('X-Slack-Signature')

            # Handle different types of requests
            if event_data.get('type') == 'url_verification':
                # Handle URL verification challenge
                return Response({'challenge': event_data['challenge']})
            
            elif event_data.get('command') == '/analyze':
                # Handle analyze command
                return self.handle_analyze_command(event_data)
            
            elif event_data.get('type') == 'event_callback':
                # Handle regular events (like mentions)
                return self.process_event(event_data)
            
            return Response({'ok': True})

        except Exception as e:
            logger.error(f"Error: {type(e).__name__} - {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def handle_analyze_command(self, command_data):
        """Handle /analyze command"""
        try:
            team_id = command_data['team_id']
            channel_id = command_data['channel_id']
            workspace = SlackWorkspace.objects.get(team_id=team_id)
            slack_service = SlackClient(workspace.bot_token)
        except SlackWorkspace.DoesNotExist:
            return Response(
                {"error": "Workspace not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        try:
            try:
                hours = int(command_data.get('text', '1'))
            except ValueError:
                hours = 1
            
            # Schedule the analysis task
            task = analyze_channel_sentiment.delay(
                workspace_id=str(workspace.uuid),
                channel_id=channel_id,
                hours=hours
            )
            
            # Send immediate response to Slack
            slack_service.send_message(channel=channel_id,
                                   text=f"🔄 Analyzing channel messages from the last {hours} hour{'s' if hours > 1 else ''}... I'll post the results here shortly!",
                                   thread_ts=command_data.get('thread_ts'))
            
            return Response({'ok': True})

        except Exception as e:
            logger.error(f"Error processing analyze command: {e}")
            slack_service.send_message(channel=channel_id,
                                    text=f"Error starting analysis: {str(e)}",
                                    thread_ts=command_data.get('thread_ts'))
        

    def process_event(self, event_data):
        """Process regular Slack events"""
        try:
            event = event_data['event']
            team_id = event_data['team_id']

            # Get workspace
            workspace = SlackWorkspace.objects.get(team_id=team_id)

            # Initialize services
            slack_service = SlackClient(workspace.bot_token)
            groq_service = GroqClient()

            if event.get('type') == 'app_mention':
                self.handle_mention(event, workspace, slack_service, groq_service)

            return Response({'ok': True})

        except Exception as e:
            logger.error(f"Error processing event: {e}")
            raise

    def handle_mention(self, event, workspace, slack_service, groq_service):
        # Get conversation history
        conversations = ConversationHistory.objects.filter(
            workspace=workspace,
            channel_id=event['channel']).order_by('-created_at')[:5]

        message_type = event.get('subtype', 'text')
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
                                           message_type=message_type,
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


class ChannelSentimentAnalysisView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            workspace_id = request.data.get('workspace_id')
            channel_id = request.data.get('channel_id')
            
            if not workspace_id or not channel_id:
                return Response(
                    {"error": "workspace_id and channel_id are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Verify workspace exists
            try:
                workspace = SlackWorkspace.objects.get(uuid=workspace_id)
            except SlackWorkspace.DoesNotExist:
                return Response(
                    {"error": "Workspace not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Schedule the analysis task
            task = analyze_channel_sentiment.delay(
                workspace_id=str(workspace_id),
                channel_id=channel_id
            )
            
            return Response({
                "message": "Sentiment analysis scheduled",
                "task_id": task.id
            })
            
        except Exception as e:
            logger.error(f"Error scheduling sentiment analysis: {e}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
