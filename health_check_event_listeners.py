#!/usr/bin/env python3
"""
Event Listeners Health Check Script
Monitors the health of the event listener system in production
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timedelta

# Add Zulip to path
sys.path.insert(0, '/srv/zulip')  # Adjust path for your deployment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.prod_settings')

try:
    import django
    django.setup()
    from zerver.event_listeners.models import EventListener, EventLog, ListenerStats
    from zerver.event_listeners.registry import event_listener_registry
    DJANGO_AVAILABLE = True
except Exception as e:
    print(f"Warning: Django not available: {e}")
    DJANGO_AVAILABLE = False

class EventListenersHealthCheck:
    def __init__(self):
        self.checks = []
        self.warnings = []
        self.errors = []
        
    def add_check(self, name, status, message, details=None):
        """Add a health check result"""
        result = {
            'name': name,
            'status': status,  # 'ok', 'warning', 'error'
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        self.checks.append(result)
        
        if status == 'warning':
            self.warnings.append(result)
        elif status == 'error':
            self.errors.append(result)
    
    def check_listener_registration(self):
        """Check if all expected listeners are registered"""
        try:
            if not DJANGO_AVAILABLE:
                self.add_check('listener_registration', 'error', 'Django not available')
                return
                
            registered = event_listener_registry.list_listeners()
            expected_count = 5
            
            if len(registered) == expected_count:
                self.add_check('listener_registration', 'ok', 
                             f'All {expected_count} listeners registered', 
                             {'listeners': registered})
            elif len(registered) > 0:
                self.add_check('listener_registration', 'warning', 
                             f'Only {len(registered)}/{expected_count} listeners registered',
                             {'listeners': registered})
            else:
                self.add_check('listener_registration', 'error', 
                             'No listeners registered')
                
        except Exception as e:
            self.add_check('listener_registration', 'error', 
                         f'Failed to check registration: {e}')
    
    def check_database_connectivity(self):
        """Check database connectivity and models"""
        try:
            if not DJANGO_AVAILABLE:
                self.add_check('database', 'error', 'Django not available')
                return
                
            # Test basic model access
            listener_count = EventListener.objects.count()
            log_count = EventLog.objects.count()
            stats_count = ListenerStats.objects.count()
            
            self.add_check('database', 'ok', 'Database accessible', {
                'listeners': listener_count,
                'logs': log_count,
                'stats': stats_count
            })
            
        except Exception as e:
            self.add_check('database', 'error', 
                         f'Database connectivity failed: {e}')
    
    def check_recent_activity(self):
        """Check for recent event processing activity"""
        try:
            if not DJANGO_AVAILABLE:
                self.add_check('recent_activity', 'error', 'Django not available')
                return
                
            # Check for events in last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            recent_events = EventLog.objects.filter(timestamp__gte=one_hour_ago).count()
            
            if recent_events > 0:
                self.add_check('recent_activity', 'ok', 
                             f'{recent_events} events processed in last hour')
            else:
                self.add_check('recent_activity', 'warning', 
                             'No events processed in last hour')
                
        except Exception as e:
            self.add_check('recent_activity', 'error', 
                         f'Failed to check recent activity: {e}')
    
    def check_error_rate(self):
        """Check error rate in recent events"""
        try:
            if not DJANGO_AVAILABLE:
                self.add_check('error_rate', 'error', 'Django not available')
                return
                
            # Check last 1000 events
            recent_events = EventLog.objects.order_by('-timestamp')[:1000]
            
            if recent_events:
                total = len(recent_events)
                failed = sum(1 for event in recent_events if not event.success)
                error_rate = (failed / total) * 100
                
                if error_rate < 1:
                    self.add_check('error_rate', 'ok', 
                                 f'Error rate: {error_rate:.2f}%')
                elif error_rate < 5:
                    self.add_check('error_rate', 'warning', 
                                 f'Error rate: {error_rate:.2f}%')
                else:
                    self.add_check('error_rate', 'error', 
                                 f'High error rate: {error_rate:.2f}%')
            else:
                self.add_check('error_rate', 'warning', 'No recent events to analyze')
                
        except Exception as e:
            self.add_check('error_rate', 'error', 
                         f'Failed to check error rate: {e}')
    
    def check_processing_performance(self):
        """Check average processing times"""
        try:
            if not DJANGO_AVAILABLE:
                self.add_check('processing_performance', 'error', 'Django not available')
                return
                
            # Check last 100 successful events
            recent_events = EventLog.objects.filter(
                success=True
            ).order_by('-timestamp')[:100]
            
            if recent_events:
                times = [event.processing_time for event in recent_events]
                avg_time = sum(times) / len(times)
                max_time = max(times)
                
                if avg_time < 100:  # Less than 100ms
                    self.add_check('processing_performance', 'ok', 
                                 f'Avg processing time: {avg_time:.2f}ms')
                elif avg_time < 500:  # Less than 500ms
                    self.add_check('processing_performance', 'warning', 
                                 f'Slow avg processing time: {avg_time:.2f}ms')
                else:
                    self.add_check('processing_performance', 'error', 
                                 f'Very slow processing time: {avg_time:.2f}ms')
            else:
                self.add_check('processing_performance', 'warning', 
                             'No recent successful events to analyze')
                
        except Exception as e:
            self.add_check('processing_performance', 'error', 
                         f'Failed to check performance: {e}')
    
    def check_web_ui(self, base_url='http://localhost:9991'):
        """Check if web UI is accessible"""
        try:
            response = requests.get(f'{base_url}/event-listeners/', timeout=5)
            
            if response.status_code in [200, 302, 403]:  # 403 is expected for non-admin
                self.add_check('web_ui', 'ok', 'Web UI is accessible')
            else:
                self.add_check('web_ui', 'warning', 
                             f'Web UI returned status {response.status_code}')
                
        except requests.exceptions.ConnectionError:
            self.add_check('web_ui', 'error', 'Cannot connect to web UI')
        except Exception as e:
            self.add_check('web_ui', 'error', f'Web UI check failed: {e}')
    
    def run_all_checks(self):
        """Run all health checks"""
        print("Running Event Listeners Health Checks...")
        print("=" * 50)
        
        self.check_listener_registration()
        self.check_database_connectivity()
        self.check_recent_activity()
        self.check_error_rate()
        self.check_processing_performance()
        self.check_web_ui()
        
        return self.generate_report()
    
    def generate_report(self):
        """Generate health check report"""
        total_checks = len(self.checks)
        ok_checks = len([c for c in self.checks if c['status'] == 'ok'])
        warning_checks = len(self.warnings)
        error_checks = len(self.errors)
        
        # Overall status
        if error_checks > 0:
            overall_status = 'CRITICAL'
        elif warning_checks > 0:
            overall_status = 'WARNING'
        else:
            overall_status = 'HEALTHY'
        
        report = {
            'overall_status': overall_status,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_checks': total_checks,
                'ok': ok_checks,
                'warnings': warning_checks,
                'errors': error_checks
            },
            'checks': self.checks,
            'warnings': self.warnings,
            'errors': self.errors
        }
        
        return report
    
    def print_report(self, report):
        """Print human-readable report"""
        status_colors = {
            'HEALTHY': '\033[92m',     # Green
            'WARNING': '\033[93m',     # Yellow  
            'CRITICAL': '\033[91m',    # Red
        }
        reset_color = '\033[0m'
        
        status = report['overall_status']
        color = status_colors.get(status, '')
        
        print(f"\n{color}Overall Status: {status}{reset_color}")
        print(f"Timestamp: {report['timestamp']}")
        print(f"Summary: {report['summary']['ok']} OK, {report['summary']['warnings']} Warnings, {report['summary']['errors']} Errors")
        
        print("\nDetailed Results:")
        print("-" * 50)
        
        for check in report['checks']:
            status_symbol = {
                'ok': '✓',
                'warning': '⚠',
                'error': '✗'
            }.get(check['status'], '?')
            
            print(f"{status_symbol} {check['name']}: {check['message']}")
            if check.get('details'):
                print(f"   Details: {check['details']}")
        
        if report['errors']:
            print(f"\n{status_colors['CRITICAL']}CRITICAL ISSUES:{reset_color}")
            for error in report['errors']:
                print(f"  ✗ {error['name']}: {error['message']}")
        
        if report['warnings']:
            print(f"\n{status_colors['WARNING']}WARNINGS:{reset_color}")
            for warning in report['warnings']:
                print(f"  ⚠ {warning['name']}: {warning['message']}")
        
        return report['overall_status'] == 'HEALTHY'

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Event Listeners Health Check')
    parser.add_argument('--json', action='store_true', 
                       help='Output results in JSON format')
    parser.add_argument('--url', default='http://localhost:9991',
                       help='Base URL for web UI check')
    parser.add_argument('--exit-code', action='store_true',
                       help='Exit with non-zero code if issues found')
    
    args = parser.parse_args()
    
    checker = EventListenersHealthCheck()
    report = checker.run_all_checks()
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        is_healthy = checker.print_report(report)
        
        if args.exit_code and not is_healthy:
            sys.exit(1)
    
    return report

if __name__ == '__main__':
    main()