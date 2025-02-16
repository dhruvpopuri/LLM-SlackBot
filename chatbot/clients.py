import groq
from django.conf import settings
import logging
import hmac
import hashlib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GroqClient:

    def __init__(self, api_key=None):
        self.client = groq.Groq(api_key=settings.GROQ_API_KEY)

    def get_response(self, messages, model="mixtral-8x7b-32768"):
        """Get response from Groq API"""
        try:
            completion = self.client.chat.completions.create(
                messages=messages,
                model=model,
                temperature=0.7,
                max_tokens=1024)
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

    def get_vision_response(self, messages):
        """Get response from Groq Vision API"""
        try:
            completion = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.2-11b-vision-preview",
                temperature=0.7,
                max_tokens=1024)
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq Vision API error: {e}")
            raise

class SlackClient:

    def __init__(self, bot_token=None):
        self.client = WebClient(token=bot_token) if bot_token else None

    @staticmethod
    def verify_signature(request_body, timestamp, signature):
        """Verify the request signature from Slack"""
        base = f"v0:{timestamp}:{request_body}"
        print(settings.SLACK_SIGNING_SECRET)
        computed_signature = f"v0={hmac.new(settings.SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(computed_signature, signature)

    def send_message(self, channel, text, thread_ts=None):
        """Send a message to a Slack channel"""
        try:
            response = self.client.chat_postMessage(channel=channel,
                                                    text=text,
                                                    thread_ts=thread_ts)
            return response
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            raise

    def get_file_info(self, file_id):
        """Get file information from Slack"""
        try:
            response = self.client.files_info(file=file_id)
            return response['file']
        except SlackApiError as e:
            logger.error(f"Error getting file info: {e}")
            raise

    def get_conversation_history(self, channel, limit=100, thread_ts=None, hours_ago=1):
        """
        Get conversation history from a Slack channel
        
        Args:
            channel (str): The channel ID to fetch messages from
            limit (int): Maximum number of messages to return (default: 100)
            thread_ts (str): If provided, fetch replies from this thread
            hours_ago (int): Number of hours to look back (default: 1)
        
        Returns:
            list: List of message objects from the conversation
        """
        try:
            # Calculate timestamp for X hours ago
            time_ago = int((datetime.now() - timedelta(hours=hours_ago)).timestamp())
            
            if thread_ts:
                response = self.client.conversations_replies(
                    channel=channel,
                    ts=thread_ts,
                    limit=limit,
                    oldest=time_ago
                )
                return response['messages']
            else:
                response = self.client.conversations_history(
                    channel=channel,
                    limit=limit,
                    oldest=time_ago
                )
                return response['messages']
        except SlackApiError as e:
            logger.error(f"Error getting conversation history: {e}")
            raise
