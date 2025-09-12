# AI Mentoring System Implementation Guide

## Overview

This document provides a complete implementation guide for creating an AI-powered mentoring system using Zulip's event system. The system will:

1. Listen for student-mentor messages
2. Learn from messaging patterns
3. Generate AI responses with human-like delays
4. Mimic mentor communication styles

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│  Message Event  │───▶│  Event Listener  │───▶│ Pattern Analyzer│
│  (from student) │    │                  │    │                │
└─────────────────┘    └──────────────────┘    └────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────┐
│ Delayed Response│◀───│Response Scheduler│◀───│   LLM Engine   │
│                 │    │                  │    │                │
└─────────────────┘    └──────────────────┘    └────────────────┘
```

## Event System Reference

### Which Events to Use

Based on Zulip's event system, you should use:
- **Primary Event**: `message` - Captures new messages sent
- **Secondary Events**: `update_message_flags` - Track read/unread status

### Event Code Locations

1. **Event Generation**: `/Users/straxs/Work/zulip/zerver/actions/message_send.py`
   - Function: `do_send_messages()` - Creates and sends message events
   
2. **Event Distribution**: `/Users/straxs/Work/zulip/zerver/tornado/django_api.py`
   - Function: `send_event_on_commit()` - Distributes events to clients

3. **Event Types Definition**: `/Users/straxs/Work/zulip/zerver/lib/event_types.py`
   - Contains all event type definitions including `EventMessage`

4. **Event Queue Processing**: `/Users/straxs/Work/zulip/zerver/tornado/event_queue.py`
   - Handles event queue management and processing

## Implementation Steps

### Step 1: Create Database Models

First, create database models to store learning data:

```python
# File: zerver/models/ai_mentoring.py

from django.db import models
from zerver.models import UserProfile, Realm

class MentorStudentRelation(models.Model):
    """Tracks mentor-student relationships"""
    mentor = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='mentees')
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='mentors')
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

class MessagePattern(models.Model):
    """Stores learned messaging patterns"""
    mentor = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    
    # Pattern characteristics
    average_response_time = models.IntegerField(help_text="Average response time in seconds")
    common_phrases = models.JSONField(default=list, help_text="Commonly used phrases")
    message_length_avg = models.IntegerField(help_text="Average message length")
    communication_style = models.CharField(max_length=50, help_text="formal/casual/mixed")
    
    # Timing patterns
    typical_active_hours = models.JSONField(default=list, help_text="Hours when mentor is typically active")
    response_delay_pattern = models.JSONField(default=dict, help_text="Response delay patterns")
    
    updated_at = models.DateTimeField(auto_now=True)

class ConversationContext(models.Model):
    """Stores conversation context for better AI responses"""
    mentor = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200)
    context_summary = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
```

### Step 2: Create Migration

```python
# File: zerver/migrations/XXXX_add_ai_mentoring_models.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('zerver', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='MentorStudentRelation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('mentor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentees', to='zerver.UserProfile')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mentors', to='zerver.UserProfile')),
                ('realm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm')),
            ],
        ),
        # Add other models...
    ]
```

### Step 3: Create Event Listener

```python
# File: zerver/lib/ai_mentoring_listener.py

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.conf import settings
from django.utils import timezone

from zerver.actions.message_send import do_send_messages, internal_prep_private_message
from zerver.models import UserProfile, Message, Recipient
from zerver.models.ai_mentoring import MentorStudentRelation, MessagePattern, ConversationContext

logger = logging.getLogger(__name__)

class AIMentoringSystem:
    """Main AI Mentoring System Class"""
    
    def __init__(self):
        self.llm_client = self._initialize_llm()
        self.pending_responses = {}
        
    def _initialize_llm(self):
        """Initialize LLM client (OpenAI, Anthropic, etc.)"""
        # Initialize your preferred LLM client here
        import openai
        return openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def handle_message_event(self, event: Dict) -> None:
        """Main handler for message events"""
        if event.get('type') != 'message':
            return
            
        message_data = event['message']
        
        # Check if this is a student messaging a mentor
        mentor_student_pair = self._identify_mentor_student_interaction(message_data)
        if not mentor_student_pair:
            return
            
        mentor, student = mentor_student_pair
        
        # Learn from the message
        self._learn_from_message(message_data, mentor, student)
        
        # Schedule AI response
        self._schedule_ai_response(message_data, mentor, student)
    
    def _identify_mentor_student_interaction(self, message_data: Dict) -> Optional[tuple]:
        """Identify if this is a mentor-student interaction"""
        sender_id = message_data['sender_id']
        
        # Check if message is private
        if message_data['type'] != 'private':
            return None
            
        # Get recipient IDs
        recipient_ids = []
        for recipient in message_data.get('display_recipient', []):
            if recipient['id'] != sender_id:
                recipient_ids.append(recipient['id'])
        
        if len(recipient_ids) != 1:
            return None  # Only handle 1-on-1 conversations
            
        recipient_id = recipient_ids[0]
        
        # Check if there's a mentor-student relationship
        try:
            relation = MentorStudentRelation.objects.get(
                mentor_id=recipient_id,
                student_id=sender_id,
                is_active=True
            )
            return (relation.mentor, relation.student)
        except MentorStudentRelation.DoesNotExist:
            return None
    
    def _learn_from_message(self, message_data: Dict, mentor: UserProfile, student: UserProfile) -> None:
        """Learn patterns from mentor-student messages"""
        sender_id = message_data['sender_id']
        content = message_data['content']
        timestamp = datetime.fromtimestamp(message_data['timestamp'])
        
        # Get or create pattern record
        pattern, created = MessagePattern.objects.get_or_create(
            mentor=mentor,
            student=student,
            defaults={
                'average_response_time': 300,  # 5 minutes default
                'common_phrases': [],
                'message_length_avg': len(content),
                'communication_style': 'mixed',
                'typical_active_hours': [],
                'response_delay_pattern': {}
            }
        )
        
        # Update patterns based on new message
        if sender_id == mentor.id:  # Message from mentor
            self._update_mentor_patterns(pattern, content, timestamp)
        
        pattern.save()
    
    def _update_mentor_patterns(self, pattern: MessagePattern, content: str, timestamp: datetime) -> None:
        """Update mentor communication patterns"""
        # Update common phrases
        phrases = self._extract_phrases(content)
        pattern.common_phrases = list(set(pattern.common_phrases + phrases))[:50]  # Keep top 50
        
        # Update message length average
        current_avg = pattern.message_length_avg or 0
        pattern.message_length_avg = int((current_avg + len(content)) / 2)
        
        # Update active hours
        hour = timestamp.hour
        if hour not in pattern.typical_active_hours:
            pattern.typical_active_hours.append(hour)
        
        # Update communication style
        pattern.communication_style = self._analyze_communication_style(content)
    
    def _extract_phrases(self, content: str) -> List[str]:
        """Extract common phrases from message content"""
        # Simple phrase extraction - can be enhanced with NLP
        import re
        
        # Remove URLs, mentions, and clean up
        content = re.sub(r'http\S+|@\w+', '', content)
        content = content.lower().strip()
        
        # Extract phrases (3+ words)
        words = content.split()
        phrases = []
        
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            if len(phrase) > 10:  # Only meaningful phrases
                phrases.append(phrase)
        
        return phrases
    
    def _analyze_communication_style(self, content: str) -> str:
        """Analyze communication style from message content"""
        formal_indicators = ['please', 'thank you', 'would you', 'could you']
        casual_indicators = ['hey', 'yeah', 'cool', 'awesome', 'lol']
        
        content_lower = content.lower()
        formal_count = sum(1 for indicator in formal_indicators if indicator in content_lower)
        casual_count = sum(1 for indicator in casual_indicators if indicator in content_lower)
        
        if formal_count > casual_count:
            return 'formal'
        elif casual_count > formal_count:
            return 'casual'
        else:
            return 'mixed'
    
    def _schedule_ai_response(self, message_data: Dict, mentor: UserProfile, student: UserProfile) -> None:
        """Schedule AI response with human-like delay"""
        # Get learned patterns
        try:
            pattern = MessagePattern.objects.get(mentor=mentor, student=student)
        except MessagePattern.DoesNotExist:
            pattern = None
        
        # Calculate response delay
        delay = self._calculate_response_delay(pattern, message_data)
        
        # Schedule the response
        asyncio.create_task(self._delayed_ai_response(
            message_data, mentor, student, delay
        ))
    
    def _calculate_response_delay(self, pattern: Optional[MessagePattern], message_data: Dict) -> int:
        """Calculate human-like response delay"""
        base_delay = 30  # Base 30 seconds
        
        if pattern and pattern.average_response_time:
            base_delay = pattern.average_response_time
        
        # Add randomness for human-like behavior
        variation = random.randint(-base_delay // 3, base_delay // 2)
        delay = max(10, base_delay + variation)  # Minimum 10 seconds
        
        # Consider message urgency (basic implementation)
        content = message_data['content'].lower()
        urgent_keywords = ['urgent', 'help', 'asap', 'emergency']
        
        if any(keyword in content for keyword in urgent_keywords):
            delay = delay // 3  # Respond faster to urgent messages
        
        return delay
    
    async def _delayed_ai_response(self, message_data: Dict, mentor: UserProfile, 
                                 student: UserProfile, delay: int) -> None:
        """Send AI response after calculated delay"""
        await asyncio.sleep(delay)
        
        try:
            # Generate AI response
            response_content = await self._generate_ai_response(message_data, mentor, student)
            
            if response_content:
                # Send the response
                self._send_response(response_content, mentor, student)
                
        except Exception as e:
            logger.error(f"Error sending AI response: {e}")
    
    async def _generate_ai_response(self, message_data: Dict, mentor: UserProfile, 
                                  student: UserProfile) -> Optional[str]:
        """Generate AI response using LLM"""
        try:
            # Get conversation context
            context = self._get_conversation_context(mentor, student)
            
            # Get mentor patterns
            pattern = MessagePattern.objects.filter(mentor=mentor, student=student).first()
            
            # Build prompt
            prompt = self._build_ai_prompt(
                message_data['content'], 
                context, 
                pattern, 
                mentor, 
                student
            )
            
            # Call LLM
            response = await self.llm_client.chat.completions.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message_data['content']}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return None
    
    def _build_ai_prompt(self, student_message: str, context: str, 
                        pattern: Optional[MessagePattern], mentor: UserProfile, 
                        student: UserProfile) -> str:
        """Build prompt for LLM to mimic mentor's style"""
        
        base_prompt = f"""You are an AI assistant mimicking {mentor.full_name}, a mentor responding to their student {student.full_name}.

CRITICAL INSTRUCTIONS:
1. Respond EXACTLY as {mentor.full_name} would, using their communication style and patterns
2. Keep responses helpful, supportive, and educational
3. Stay in character as the mentor at all times

MENTOR'S COMMUNICATION STYLE:"""
        
        if pattern:
            style_info = f"""
- Communication Style: {pattern.communication_style}
- Average Message Length: ~{pattern.message_length_avg} characters
- Common Phrases: {', '.join(pattern.common_phrases[:10])}
- Typical Response Style: {"Professional and structured" if pattern.communication_style == 'formal' else "Friendly and conversational" if pattern.communication_style == 'casual' else "Balanced approach"}
"""
        else:
            style_info = """
- Communication Style: Professional yet approachable
- Be supportive and encouraging
- Provide guidance and ask thoughtful questions
"""
        
        conversation_context = f"""
CONVERSATION CONTEXT:
{context}

STUDENT'S MESSAGE:
{student_message}

Respond as {mentor.full_name} would, maintaining their established communication patterns while being helpful and supportive."""

        return base_prompt + style_info + conversation_context
    
    def _get_conversation_context(self, mentor: UserProfile, student: UserProfile) -> str:
        """Get recent conversation context"""
        try:
            context_obj = ConversationContext.objects.filter(
                mentor=mentor, 
                student=student
            ).first()
            
            if context_obj:
                return context_obj.context_summary
            else:
                return "This is the beginning of your mentoring conversation."
                
        except Exception:
            return "This is the beginning of your mentoring conversation."
    
    def _send_response(self, content: str, mentor: UserProfile, student: UserProfile) -> None:
        """Send AI response as the mentor"""
        try:
            # Create message request
            message_request = internal_prep_private_message(
                sender=mentor,
                recipient_user=student,
                content=content
            )
            
            if message_request:
                # Send the message
                do_send_messages([message_request])
                logger.info(f"AI response sent from {mentor.full_name} to {student.full_name}")
                
        except Exception as e:
            logger.error(f"Error sending response: {e}")


# Initialize the AI mentoring system
ai_mentoring_system = AIMentoringSystem()
```

### Step 4: Integration with Event System

There are multiple ways to integrate with Zulip's event system:

#### Option 1: Python Client API (Recommended)

```python
# File: scripts/ai_mentoring_service.py

#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.settings')
django.setup()

import zulip
from zerver.lib.ai_mentoring_listener import ai_mentoring_system

def main():
    # Initialize Zulip client
    client = zulip.Client(config_file="~/.zuliprc-ai-bot")
    
    def handle_event(event):
        """Handle all Zulip events"""
        ai_mentoring_system.handle_message_event(event)
    
    print("Starting AI Mentoring Service...")
    
    # Listen for all events
    client.call_on_each_event(
        handle_event,
        event_types=['message']  # Only listen for message events
    )

if __name__ == "__main__":
    main()
```

#### Option 2: Django Management Command

```python
# File: zerver/management/commands/ai_mentoring_daemon.py

from django.core.management.base import BaseCommand
import zulip
from zerver.lib.ai_mentoring_listener import ai_mentoring_system

class Command(BaseCommand):
    help = 'Run AI Mentoring System as a daemon'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting AI Mentoring Daemon...')
        
        # Initialize Zulip client
        client = zulip.Client(config_file="zuliprc-ai-bot")
        
        def handle_event(event):
            ai_mentoring_system.handle_message_event(event)
        
        # Start listening
        client.call_on_each_event(
            handle_event,
            event_types=['message']
        )
```

### Step 5: Configuration and Setup

#### 1. Add Settings

```python
# File: zproject/settings.py

# Add to the end of the file
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# AI Mentoring Configuration
AI_MENTORING_ENABLED = True
AI_MENTORING_MIN_DELAY = 10  # Minimum response delay in seconds
AI_MENTORING_MAX_DELAY = 1800  # Maximum response delay in seconds
```

#### 2. Create Bot User

```bash
# Create a bot user for the AI system
python manage.py shell
```

```python
# In Django shell
from zerver.models import UserProfile, Realm
from zerver.actions.users import do_create_user

realm = Realm.objects.get(string_id='your-realm')
bot_user = do_create_user(
    email='ai-mentor-bot@yourdomain.com',
    password=None,
    realm=realm,
    full_name='AI Mentor Bot',
    bot_type=UserProfile.DEFAULT_BOT,
    is_bot=True
)
```

#### 3. Set up Mentor-Student Relationships

```python
# File: zerver/management/commands/setup_mentoring_relationships.py

from django.core.management.base import BaseCommand
from zerver.models import UserProfile
from zerver.models.ai_mentoring import MentorStudentRelation

class Command(BaseCommand):
    help = 'Setup mentor-student relationships'
    
    def add_arguments(self, parser):
        parser.add_argument('--mentor-email', type=str, required=True)
        parser.add_argument('--student-email', type=str, required=True)
    
    def handle(self, *args, **options):
        try:
            mentor = UserProfile.objects.get(email=options['mentor_email'])
            student = UserProfile.objects.get(email=options['student_email'])
            
            relation, created = MentorStudentRelation.objects.get_or_create(
                mentor=mentor,
                student=student,
                realm=mentor.realm
            )
            
            if created:
                self.stdout.write(f'Created mentoring relationship: {mentor.full_name} -> {student.full_name}')
            else:
                self.stdout.write(f'Relationship already exists: {mentor.full_name} -> {student.full_name}')
                
        except UserProfile.DoesNotExist as e:
            self.stdout.write(f'Error: {e}')
```

### Step 6: Running the System

#### 1. Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

#### 2. Set up Environment

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

#### 3. Create Bot Configuration

```bash
# Create ~/.zuliprc-ai-bot
cat > ~/.zuliprc-ai-bot << EOF
[api]
email=ai-mentor-bot@yourdomain.com
key=your-bot-api-key
site=https://your-zulip-server.com
EOF
```

#### 4. Set up Relationships

```bash
python manage.py setup_mentoring_relationships --mentor-email mentor@domain.com --student-email student@domain.com
```

#### 5. Start the AI Service

```bash
# Option 1: Using script
python scripts/ai_mentoring_service.py

# Option 2: Using management command
python manage.py ai_mentoring_daemon
```

### Docker Integration

#### Add to Docker Compose

```yaml
# File: docker-compose.yml (add this service)

services:
  # ... existing services ...
  
  ai-mentoring:
    build: .
    command: python manage.py ai_mentoring_daemon
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - database
      - zulip
    volumes:
      - ./:/app
    restart: unless-stopped
```

## Testing the System

### 1. Basic Test

```python
# File: test_ai_mentoring.py

import unittest
from zerver.lib.ai_mentoring_listener import AIMentoringSystem
from zerver.models.ai_mentoring import MentorStudentRelation
from zerver.lib.test_classes import ZulipTestCase

class TestAIMentoring(ZulipTestCase):
    def setUp(self):
        super().setUp()
        self.ai_system = AIMentoringSystem()
        
        # Create test users
        self.mentor = self.example_user('hamlet')
        self.student = self.example_user('othello')
        
        # Create relationship
        MentorStudentRelation.objects.create(
            mentor=self.mentor,
            student=self.student,
            realm=self.mentor.realm
        )
    
    def test_mentor_student_identification(self):
        """Test identification of mentor-student interactions"""
        message_data = {
            'type': 'private',
            'sender_id': self.student.id,
            'display_recipient': [
                {'id': self.student.id},
                {'id': self.mentor.id}
            ]
        }
        
        result = self.ai_system._identify_mentor_student_interaction(message_data)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], self.mentor)
        self.assertEqual(result[1], self.student)
```

### 2. Run Tests

```bash
python manage.py test zerver.tests.test_ai_mentoring -v 2
```

## Monitoring and Logging

### Add Logging Configuration

```python
# File: zproject/settings.py

LOGGING = {
    # ... existing logging config ...
    'loggers': {
        # ... existing loggers ...
        'ai_mentoring': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}
```

## Security Considerations

1. **API Key Security**: Store LLM API keys securely using environment variables
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Data Privacy**: Ensure conversation data is handled according to privacy policies
4. **Content Filtering**: Add content filtering to prevent inappropriate responses

## Performance Optimization

1. **Async Processing**: Use async/await for LLM calls
2. **Caching**: Cache frequently used patterns and responses
3. **Database Indexing**: Add proper database indexes for performance
4. **Response Queuing**: Queue responses during high load

## Future Enhancements

1. **Multi-language Support**: Support for different languages
2. **Advanced NLP**: Better pattern recognition using advanced NLP
3. **Sentiment Analysis**: Understand emotional context
4. **Learning Feedback**: Allow mentors to provide feedback on AI responses
5. **Custom Personas**: Allow mentors to define custom AI personas

This implementation provides a complete AI mentoring system that integrates with Zulip's event system, learns from messaging patterns, and provides human-like responses with appropriate delays.