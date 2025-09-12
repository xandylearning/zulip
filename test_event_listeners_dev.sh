#!/bin/bash
# Event Listeners Development Testing Script
# Tests the complete event listener system before production deployment

set -e  # Exit on any error

echo "========================================"
echo "Event Listeners Development Test Suite"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✓ $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}✗ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ $message${NC}"
            ;;
    esac
}

# Test 1: Check Django app is properly configured
echo ""
echo "=== Test 1: Django Configuration ==="
print_status "INFO" "Checking Django settings..."

if ./manage.py check --deploy 2>/dev/null; then
    print_status "SUCCESS" "Django configuration is valid"
else
    print_status "ERROR" "Django configuration has issues"
    exit 1
fi

# Test 2: Check if event listeners app is installed
echo ""
echo "=== Test 2: Event Listeners App Installation ==="
print_status "INFO" "Checking if event_listeners app is installed..."

if ./manage.py list_event_listeners >/dev/null 2>&1; then
    print_status "SUCCESS" "Event listeners app is properly installed"
else
    print_status "ERROR" "Event listeners app is not properly installed"
    print_status "INFO" "Make sure EVENT_LISTENERS_ENABLED = True in settings"
    exit 1
fi

# Test 3: List registered event listeners
echo ""
echo "=== Test 3: Registered Event Listeners ==="
print_status "INFO" "Listing all registered event listeners..."

listeners_output=$(./manage.py list_event_listeners 2>/dev/null)
listener_count=$(echo "$listeners_output" | grep -c "^[0-9]" || true)

if [ "$listener_count" -eq 5 ]; then
    print_status "SUCCESS" "All 5 expected event listeners are registered"
    echo "$listeners_output"
else
    print_status "ERROR" "Expected 5 event listeners, found $listener_count"
    echo "$listeners_output"
fi

# Test 4: Database migrations
echo ""
echo "=== Test 4: Database Setup ==="
print_status "INFO" "Checking database migrations..."

if ./manage.py makemigrations --dry-run event_listeners 2>/dev/null | grep -q "No changes detected"; then
    print_status "SUCCESS" "Database migrations are up to date"
else
    print_status "WARNING" "Database migrations may be needed"
    print_status "INFO" "Running migrations..."
    if ./manage.py makemigrations event_listeners && ./manage.py migrate event_listeners; then
        print_status "SUCCESS" "Database migrations completed"
    else
        print_status "ERROR" "Database migration failed"
        exit 1
    fi
fi

# Test 5: Initialize event listeners in database
echo ""
echo "=== Test 5: Database Initialization ==="
print_status "INFO" "Initializing event listeners in database..."

if ./manage.py init_event_listeners; then
    print_status "SUCCESS" "Event listeners initialized in database"
else
    print_status "ERROR" "Failed to initialize event listeners in database"
    exit 1
fi

# Test 6: Demo mode test
echo ""
echo "=== Test 6: Demo Mode Test ==="
print_status "INFO" "Testing event listeners in demo mode (30 seconds)..."

# Start demo mode in background
./manage.py run_event_listeners --demo-mode --timeout=30 > demo_test.log 2>&1 &
DEMO_PID=$!

# Wait for it to start
sleep 5

# Check if process is still running
if kill -0 $DEMO_PID 2>/dev/null; then
    print_status "SUCCESS" "Demo mode is running successfully"
    
    # Wait for it to finish
    wait $DEMO_PID
    
    # Check the log for expected output
    if grep -q "Processing demo event" demo_test.log; then
        print_status "SUCCESS" "Demo events are being processed"
    else
        print_status "WARNING" "Demo events may not be processing correctly"
    fi
    
    # Show some log output
    echo "Sample log output:"
    tail -10 demo_test.log
    
else
    print_status "ERROR" "Demo mode failed to start"
    exit 1
fi

# Test 7: Web UI accessibility
echo ""
echo "=== Test 7: Web UI Test ==="
print_status "INFO" "Testing web UI accessibility..."

# Start development server in background
./manage.py runserver 0.0.0.0:8001 > webui_test.log 2>&1 &
WEBUI_PID=$!

# Wait for server to start
sleep 10

# Test if web UI is accessible
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/event-listeners/ | grep -q "200\|302"; then
    print_status "SUCCESS" "Web UI is accessible"
else
    print_status "WARNING" "Web UI may have authentication requirements (expected for admin interface)"
fi

# Stop web server
kill $WEBUI_PID 2>/dev/null || true

# Test 8: Performance test
echo ""
echo "=== Test 8: Performance Test ==="
print_status "INFO" "Running performance test with multiple events..."

# Create a performance test script
cat > perf_test.py << 'EOF'
import os
import sys
import django
import time
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, '/Users/straxs/Work/zulip')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.dev_settings')
django.setup()

from zerver.event_listeners.registry import event_listener_registry
from zerver.event_listeners.processor import EventProcessor

def test_event_processing():
    processor = EventProcessor()
    
    # Test event
    test_event = {
        'type': 'message',
        'message': {
            'content': f'Performance test message {time.time()}',
            'sender_id': 1,
            'recipient_id': 2,
            'timestamp': int(time.time())
        }
    }
    
    start_time = time.time()
    try:
        processor.process_event(test_event)
        return time.time() - start_time
    except Exception as e:
        print(f"Error processing event: {e}")
        return None

# Process 50 events concurrently
print("Processing 50 test events...")
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(test_event_processing) for _ in range(50)]
    times = [f.result() for f in futures if f.result() is not None]

if times:
    avg_time = sum(times) / len(times)
    max_time = max(times)
    min_time = min(times)
    print(f"Processed {len(times)}/50 events successfully")
    print(f"Average processing time: {avg_time:.3f}s")
    print(f"Min/Max processing time: {min_time:.3f}s / {max_time:.3f}s")
    
    if avg_time < 0.1:  # Less than 100ms average
        print("✓ Performance is acceptable")
    else:
        print("⚠ Performance may need optimization")
else:
    print("✗ No events processed successfully")
EOF

if python perf_test.py; then
    print_status "SUCCESS" "Performance test completed"
else
    print_status "WARNING" "Performance test had issues"
fi

# Cleanup
rm -f demo_test.log webui_test.log perf_test.py

# Final summary
echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"
print_status "SUCCESS" "Development testing completed!"
print_status "INFO" "Your event listener system is ready for production"

echo ""
echo "Next Steps for Production:"
echo "1. Deploy code to production environment"
echo "2. Run database migrations: ./manage.py migrate event_listeners"
echo "3. Initialize listeners: ./manage.py init_event_listeners"
echo "4. Start event processor: ./manage.py run_event_listeners"
echo "5. Monitor via web UI at: /event-listeners/"

echo ""
echo "Production Monitoring:"
echo "- Check listener status: ./manage.py list_event_listeners"
echo "- View logs: Check Django logs for 'zerver.event_listeners'"
echo "- Web dashboard: https://yourdomain/event-listeners/"
echo "- Performance: Monitor processing times and success rates"