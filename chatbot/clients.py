import groq
from django.conf import settings
import logging
import hmac
import hashlib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings

logger = logging.getLogger(__name__)


class GroqClient:

    def __init__(self, api_key=None):
        self.client = groq.Groq(
            api_key=settings.GROQ_API_KEY)

    def get_response(self, messages):
        """Get response from Groq API"""
        try:
            completion = self.client.chat.completions.create(
                messages=messages,
                model="mixtral-8x7b-32768",
                temperature=0.7,
                max_tokens=1024)
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
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
