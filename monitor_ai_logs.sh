#!/bin/bash
# AI Agent Log Monitoring Script

echo "🤖 AI Agent Log Monitor"
echo "Choose monitoring option:"
echo "1. All AI-related logs"
echo "2. Only AI integration triggers"
echo "3. Only AI event processing"
echo "4. Only AI errors"
echo "5. AI agent performance metrics"
echo "6. Custom search"

read -p "Enter choice (1-6): " choice

LOG_FILE="/var/log/zulip/django.log"

# For development, also check if run-dev is being used
if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️  Django log file not found at $LOG_FILE"
    echo "   If using development server, run: ./tools/run-dev 2>&1 | grep -E '(AI|ai_agent|ai_mentor)'"
    echo "   Or check: journalctl -u zulip -f | grep -E '(AI|ai_agent|ai_mentor)'"
    exit 1
fi

case $choice in
    1)
        echo "📊 Monitoring ALL AI-related logs..."
        tail -f "$LOG_FILE" | grep -E --color=always "(AI|ai_agent|ai_mentor|AI_|LANGGRAPH)"
        ;;
    2)
        echo "🔍 Monitoring AI integration triggers..."
        tail -f "$LOG_FILE" | grep -E --color=always "(AI Agent Integration|trigger_ai_agent_conversation|student.*mentor)"
        ;;
    3)
        echo "⚙️  Monitoring AI event processing..."
        tail -f "$LOG_FILE" | grep -E --color=always "(Processing AI mentor event|AI agent conversation|AI response generated|orchestrator)"
        ;;
    4)
        echo "❌ Monitoring AI errors..."
        tail -f "$LOG_FILE" | grep -E --color=always "(AI.*error|AI.*failed|AI.*exception|missing.*ID)"
        ;;
    5)
        echo "📈 Monitoring AI performance metrics..."
        tail -f "$LOG_FILE" | grep -E --color=always "(confidence|processing.*time|token.*usage|AI.*performance)"
        ;;
    6)
        read -p "Enter custom search pattern: " pattern
        echo "🔎 Monitoring logs for pattern: $pattern"
        tail -f "$LOG_FILE" | grep -E --color=always "$pattern"
        ;;
    *)
        echo "Invalid choice. Monitoring all AI logs..."
        tail -f "$LOG_FILE" | grep -E --color=always "(AI|ai_agent|ai_mentor)"
        ;;
esac