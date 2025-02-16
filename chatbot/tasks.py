from celery import shared_task
from django.conf import settings
from .models import SlackWorkspace, ConversationHistory, ChannelAnalysis
from .clients import SlackClient, GroqClient
import logging
from datetime import datetime, timedelta
import requests
import base64

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
                # Check for bot messages in multiple ways
                is_bot = (
                    bool(msg.get('bot_id')) or  # Has bot_id
                    msg.get('subtype') == 'bot_message' or  # Explicit bot message
                    bool(msg.get('app_id'))  # Message from an app
                )
                
                conv, created = ConversationHistory.objects.get_or_create(
                    workspace=workspace,
                    channel_id=channel_id,
                    message_ts=msg['ts'],
                    defaults={
                        'user_id': msg.get('user', ''),
                        'message_text': msg.get('text', ''),
                        'thread_ts': msg.get('thread_ts'),
                        'message_type': msg.get('type', 'text'),
                        'is_bot_message': is_bot
                    }
                )
                stored_messages.append(conv)

        # Handle images if present
        image_url = None
        for msg in reversed(messages):  # Look for most recent image
            if msg.get('files'):
                for file in msg['files']:
                    if file['filetype'] in ['png', 'jpg', 'jpeg']:
                        try:
                            # Get file info from Slack to get direct download URL
                            file_info = slack_client.get_file_info(file['id'])
                            direct_url = file_info.get('url_private_download', file_info.get('url_private'))
                            # Download the image using the bot token for authentication
                            response = requests.get(
                                direct_url,
                                headers={'Authorization': f"Bearer {workspace.bot_token}"},
                                allow_redirects=True  # Follow redirects
                            )
                            
                            print(f"Downloading from URL: {direct_url}")
                            print(f"Response status: {response.status_code}")
                            print(f"Response headers: {response.headers}")
                            
                            if response.status_code == 200:
                                mime_type = file['mimetype']
                                base64_image = base64.b64encode(response.content).decode('utf-8')
                                image_url = f"data:{mime_type};base64,{base64_image}"
                                print(f"Image MIME type: {mime_type}")
                                break
                        except Exception as e:
                            logger.error(f"Error downloading image: {e}")
                            continue
                if image_url:
                    break

        # Format messages for analysis, excluding bot messages
        formatted_messages = "\n".join([
            f"User {msg.user_id}: {msg.message_text}"
            for msg in stored_messages
            if not msg.is_bot_message  # Exclude bot messages
        ])

        # Add a check to ensure we have messages to analyze
        if not formatted_messages.strip():
            slack_client.send_message(
                channel=channel_id,
                text=f"⚠️ No user messages found in the last {hours} hour{'s' if hours > 1 else ''} to analyze."
            )
            return {
                "channel_id": channel_id,
                "workspace_id": workspace_id,
                "analysis": "No user messages to analyze",
                "message_count": 0
            }

        # Initialize analysis components
        image_analysis = ""
        text_analysis = ""
        
        # Handle image analysis if present
        if image_url:
            # Use vision model for image analysis
            vision_prompt = [{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this image in the context of a Slack conversation that is expressing the sentiment of a given product. What do you see? Keep it concise and under 350 words"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }]
            print(f"Vision prompt: {vision_prompt}")
            image_analysis = groq_client.get_vision_response(vision_prompt)
            print(f"Image analysis: {image_analysis}")

        text_prompt = [{
            "role": "system",
            "content": "You are an expert at analyzing conversation sentiment. Analyze all messages in the following Slack conversation with equla importance and provide: \n1. Overall sentiment (positive/negative/neutral)\n2. Key themes or topics\n3. Any notable patterns in interaction\n4. Level of engagement\nBe concise but thorough."
        }]

        # If we have image analysis, include it in the context
        if image_analysis:
            text_prompt.append({
                "role": "user",
                "content": f"An image was shared in this conversation. Here's what was observed in the image:\n\n{image_analysis}\n\nNow, analyze the following conversation in this context:\n\n{formatted_messages}"
            })
        else:
            text_prompt.append({
                "role": "user",
                "content": f"Here's the conversation to analyze:\n\n{formatted_messages}"
            })

        print(f"Text prompt: {text_prompt}")
        text_analysis = groq_client.get_response(text_prompt)

        # Combine analyses
        final_analysis = text_analysis
        if image_analysis:
            final_analysis = f"📸 *Image Analysis*:\n{image_analysis}\n\n📊 *Conversation Analysis*:\n{text_analysis}"

        # Store analysis
        channel_analysis = ChannelAnalysis.objects.create(
            workspace=workspace,
            channel_id=channel_id,
            analysis_text=final_analysis,
            message_count=len(stored_messages),
            time_window_hours=hours
        )

        # Send analysis to Slack
        slack_client.send_message(
            channel=channel_id,
            text=f"*Channel Analysis (Last {hours} hour{'s' if hours > 1 else ''})* 📊\n\n{final_analysis}"
        )

        return {
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "analysis": final_analysis,
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