from celery import shared_task
from django.conf import settings
from .models import SlackWorkspace, ConversationHistory, ChannelAnalysis
from .clients import SlackClient, GroqClient
import logging
import boto3
from datetime import datetime, timedelta
import requests
import os

logger = logging.getLogger(__name__)

@shared_task
def analyze_channel_sentiment(workspace_id, channel_id, hours=1):
    try:
        # Get workspace
        workspace = SlackWorkspace.objects.get(uuid=workspace_id)
        
        # Initialize clients
        slack_client = SlackClient(workspace.bot_token)
        groq_client = GroqClient()
        
        # Get conversation history
        messages = slack_client.get_conversation_history(
            channel=channel_id, 
            limit=100,
            hours_ago=hours
        )
        
        # Store messages in database
        stored_messages = []
        for msg in messages:
            if msg.get('text'):  # Only store messages with text
                conv, created = ConversationHistory.objects.get_or_create(
                    workspace=workspace,
                    channel_id=channel_id,
                    message_ts=msg['ts'],
                    defaults={
                        'user_id': msg.get('user', ''),
                        'message_text': msg.get('text', ''),
                        'thread_ts': msg.get('thread_ts'),
                        'message_type': msg.get('type', 'text'),
                        'is_bot_message': bool(msg.get('bot_id'))
                    }
                )
                stored_messages.append(conv)

        # Handle images if present
        image_url = None
        for msg in reversed(messages):  # Look for most recent image
            if msg.get('files'):
                for file in msg['files']:
                    if file['filetype'] in ['png', 'jpg', 'jpeg']:
                        # Upload to S3
                        s3_client = boto3.client('s3')
                        response = requests.get(file['url_private'], headers={
                            'Authorization': f"Bearer {workspace.bot_token}"
                        })
                        if response.status_code == 200:
                            s3_client.put_object(
                                Bucket=settings.AWS_BUCKET_NAME,
                                Key=f"channel_images/{workspace.team_id}/{channel_id}/{file['id']}.{file['filetype']}",
                                Body=response.content,
                                ContentType=file['mimetype'],
                                ACL='public-read'
                            )
                            image_url = f"https://{settings.AWS_BUCKET_NAME}.s3.amazonaws.com/channel_images/{workspace.team_id}/{channel_id}/{file['id']}.{file['filetype']}"
                            break
                if image_url:
                    break

        # Format messages for analysis
        formatted_messages = "\n".join([
            f"User {msg.user_id}: {msg.message_text}"
            for msg in stored_messages
        ])

        # Prepare prompt for sentiment analysis
        prompt = [{
            "role": "system",
            "content": "You are an expert at analyzing conversation sentiment. Analyze the following Slack conversation and provide: \n1. Overall sentiment (positive/negative/neutral)\n2. Key themes or topics\n3. Any notable patterns in interaction\n4. Level of engagement\nBe concise but thorough."
        }]

        if image_url:
            prompt.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Also analyze this image in the context of the conversation:"},
                    {"type": "image_url", "image_url": image_url}
                ]
            })

        prompt.append({
            "role": "user",
            "content": f"Here's the conversation to analyze:\n\n{formatted_messages}"
        })

        # Get analysis from Groq
        analysis = groq_client.get_response(prompt)

        # Store analysis
        channel_analysis = ChannelAnalysis.objects.create(
            workspace=workspace,
            channel_id=channel_id,
            analysis_text=analysis,
            message_count=len(stored_messages),
            time_window_hours=hours
        )

        # Send analysis to Slack
        slack_client.send_message(
            channel=channel_id,
            text=f"*Channel Analysis (Last {hours} hour{'s' if hours > 1 else ''})* 📊\n\n{analysis}"
        )

        return {
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "analysis": analysis,
            "message_count": len(stored_messages)
        }
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis task: {e}")
        # Notify the channel about the error
        try:
            slack_client.send_message(
                channel=channel_id,
                text=f"❌ Error performing sentiment analysis: {str(e)}"
            )
        except:
            pass
        raise 