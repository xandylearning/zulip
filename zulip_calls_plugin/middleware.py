"""
Middleware to integrate the Zulip Calls Plugin with compose functionality.
This provides a cleaner integration without modifying core Zulip templates.
"""

from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils.safestring import mark_safe
import json
import re


class ZulipCallsMiddleware:
    """Middleware to intercept and handle call creation requests"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is a call creation request that we should intercept
        if (request.method == 'POST' and
            request.path in ['/json/calls/zoom/create', '/json/calls/bigbluebutton/create'] and
            hasattr(request, 'user') and request.user.is_authenticated):

            # Check if the user wants to use our embedded calls instead
            use_embedded_calls = getattr(request.user, 'use_embedded_calls', True)

            if use_embedded_calls:
                return self._handle_embedded_call_creation(request)

        response = self.get_response(request)

        # Inject our JavaScript into HTML responses for the main app
        if (hasattr(request, 'user') and request.user.is_authenticated and
            isinstance(response, HttpResponse) and
            response.get('Content-Type', '').startswith('text/html') and
            request.path == '/'):
            response = self._inject_calls_javascript(request, response)

        return response

    def _handle_embedded_call_creation(self, request):
        """Handle embedded call creation by redirecting to our plugin"""
        try:
            # Import here to avoid circular imports
            from .views.calls import create_embedded_call
            from zerver.models import get_user_profile_by_id

            # Get the user profile
            user_profile = get_user_profile_by_id(request.user.id)

            # Extract call parameters from the original request
            is_video_call = True  # Default to video
            if request.path == '/json/calls/bigbluebutton/create':
                # BigBlueButton request format
                voice_only = request.POST.get('voice_only', 'false').lower() == 'true'
                is_video_call = not voice_only
            elif 'is_video_call' in request.POST:
                # Zoom request format
                is_video_call = request.POST.get('is_video_call', 'true').lower() == 'true'

            # Get recipient email from the current compose context
            # Since we don't have direct access to the compose state from the middleware,
            # we'll need the frontend to pass this information
            recipient_email = request.POST.get('recipient_email')

            if not recipient_email:
                # If no recipient provided, return error asking user to specify
                return JsonResponse({
                    'result': 'error',
                    'msg': 'Please specify a recipient for the call',
                    'code': 'RECIPIENT_REQUIRED'
                }, status=400)

            # Create a new request object for our embedded call
            from django.http import QueryDict
            new_post_data = QueryDict('', mutable=True)
            new_post_data['recipient_email'] = recipient_email
            new_post_data['is_video_call'] = str(is_video_call)
            new_post_data['redirect_to_meeting'] = 'true'  # Enable direct redirect

            # Update the request
            request.POST = new_post_data

            # Call our embedded call creation function
            response = create_embedded_call(request, user_profile)

            # If successful, modify the response to match expected format
            if response.status_code == 200:
                data = json.loads(response.content)
                if data.get('result') == 'success' and data.get('action') == 'redirect':
                    # Return in the format expected by Zulip's compose_call_ui
                    return JsonResponse({
                        'result': 'success',
                        'msg': 'Call created successfully',
                        'url': data['redirect_url']
                    })

            return response

        except Exception as e:
            return JsonResponse({
                'result': 'error',
                'msg': f'Failed to create call: {str(e)}',
                'code': 'EMBEDDED_CALL_ERROR'
            }, status=500)

    def _inject_calls_javascript(self, request, response):
        """Inject calls plugin JavaScript into HTML responses"""
        try:
            content = response.content.decode('utf-8')

            # Only inject if it's the main app page and not already injected
            if ('</body>' in content and
                'zulip-calls-plugin-injected' not in content and
                ('class="app"' in content or 'id="app-loading"' in content)):

                # Create the JavaScript injection
                js_injection = f'''
<!-- Zulip Calls Plugin Integration -->
<script id="zulip-calls-plugin-injected">
(function() {{
    if (typeof $ === 'undefined') {{
        console.warn('Zulip Calls Plugin: jQuery not available, retrying...');
        setTimeout(arguments.callee, 100);
        return;
    }}

    // Load the calls plugin script
    const script = document.createElement('script');
    script.src = '{request.build_absolute_uri("/static/js/embedded_calls.js")}';
    script.onload = function() {{
        console.log('Zulip Calls Plugin: Loaded successfully');
        if (window.embeddedCalls && window.embeddedCalls.overrideCallButtons) {{
            setTimeout(function() {{
                window.embeddedCalls.overrideCallButtons();
            }}, 1000);
        }}
    }};
    script.onerror = function() {{
        console.warn('Zulip Calls Plugin: Failed to load script');
    }};
    document.head.appendChild(script);
}})();
</script>
'''

                # Inject before closing body tag
                content = content.replace('</body>', js_injection + '\n</body>')
                response.content = content.encode('utf-8')
                response['Content-Length'] = len(response.content)

        except Exception as e:
            # Don't break the response if injection fails
            print(f'Zulip Calls Plugin: Failed to inject JavaScript: {e}')

        return response