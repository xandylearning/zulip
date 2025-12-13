# LMS Integration URL Configuration
from django.urls import path

from lms_integration.views import lms_user_webhook

app_name = 'lms_integration'

urlpatterns = [
    # Webhook endpoint for LMS to notify Zulip when new users are created
    path('webhook/user-created', lms_user_webhook, name='lms_user_webhook'),
]
