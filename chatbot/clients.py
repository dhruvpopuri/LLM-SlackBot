import boto3
import groq
from django.conf import settings
import time
import logging
import hmac
import hashlib
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from django.conf import settings

logger = logging.getLogger(__name__)

class GroqClient:
    def __init__(self, api_key=None):
        self.client = groq.Client(api_key=api_key or settings.GROQ_API_KEY)

    async def get_response(self, messages):
        """Get response from Groq API"""
        try:
            completion = await self.client.chat.completions.create(
                messages=messages,
                model="mixtral-8x7b-32768",
                temperature=0.7,
                max_tokens=1024
            )
            return completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise


class FileServiceClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
        )

    async def upload_file(self, file_data, file_info):
        """Upload file to S3"""
        try:
            file_key = f"uploads/{int(time.time())}_{file_info['name']}"
            await self.s3_client.put_object(
                Bucket=settings.S3_BUCKET,
                Key=file_key,
                Body=file_data,
                ContentType=file_info['mimetype']
            )
            return f"s3://{settings.S3_BUCKET}/{file_key}"
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise


logger = logging.getLogger(__name__)

class SlackClient:
    def __init__(self, bot_token=None):
        self.client = WebClient(token=bot_token) if bot_token else None

    @staticmethod
    def verify_signature(request_body, timestamp, signature):
        """Verify the request signature from Slack"""
        base = f"v0:{timestamp}:{request_body}"
        computed_signature = f"v0={hmac.new(settings.SLACK_SIGNING_SECRET.encode(), base.encode(), hashlib.sha256).hexdigest()}"
        return hmac.compare_digest(computed_signature, signature)

    async def send_message(self, channel, text, thread_ts=None):
        """Send a message to a Slack channel"""
        try:
            response = await self.client.chat_postMessage(
                channel=channel,
                text=text,
                thread_ts=thread_ts
            )
            return response
        except SlackApiError as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def get_file_info(self, file_id):
        """Get file information from Slack"""
        try:
            response = await self.client.files_info(file=file_id)
            return response['file']
        except SlackApiError as e:
            logger.error(f"Error getting file info: {e}")
            raise
