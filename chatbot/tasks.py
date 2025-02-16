from celery import shared_task
from .models import SlackWorkspace, ConversationHistory
from .clients import SlackClient, GroqClient
import logging

logger = logging.getLogger(__name__)

@shared_task
def analyze_channel_sentiment(workspace_id, channel_id):
    try:
        # Get workspace
        workspace = SlackWorkspace.objects.get(uuid=workspace_id)
        
        # Initialize clients
        slack_client = SlackClient(workspace.bot_token)
        groq_client = GroqClient()
        
        # Get conversation history from Slack
        messages = slack_client.get_conversation_history(channel=channel_id, limit=100)
        
        # Format messages for analysis
        formatted_messages = "\n".join([
            f"User {msg.get('user')}: {msg.get('text')}"
            for msg in messages
            if msg.get('text')  # Filter out messages with no text
        ])
        
        # Prepare prompt for sentiment analysis
        prompt = [{
            "role": "system",
            "content": "You are an expert at analyzing conversation sentiment. Analyze the following Slack conversation and provide: \n1. Overall sentiment (positive/negative/neutral)\n2. Key themes or topics\n3. Any notable patterns in interaction\n4. Level of engagement\nBe concise but thorough."
        }, {
            "role": "user",
            "content": f"Here's the conversation to analyze:\n\n{formatted_messages}"
        }]
        
        # Get analysis from Groq
        analysis = groq_client.get_response(prompt)
        
        return {
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "analysis": analysis,
            "message_count": len(messages)
        }
        
    except Exception as e:
        logger.error(f"Error in sentiment analysis task: {e}")
        raise 