"""
Integration utilities for the Zulip Calls Plugin

This module provides utilities to integrate the plugin with Zulip's core functionality,
including template injection and JavaScript loading.
"""

import os
from django.conf import settings
from django.template.loader import render_to_string


def inject_embedded_calls_script():
    """
    Inject the embedded calls script into Zulip's main template.
    This should be called during plugin installation.
    """
    try:
        # Find Zulip's main app template
        app_template_path = None
        for template_dir in settings.TEMPLATES[0]['DIRS']:
            potential_path = os.path.join(template_dir, 'zerver', 'app.html')
            if os.path.exists(potential_path):
                app_template_path = potential_path
                break

        if not app_template_path:
            print("Warning: Could not find Zulip's main app template")
            return False

        # Read the current template
        with open(app_template_path, 'r') as f:
            template_content = f.read()

        # Check if our script is already injected
        if 'embedded_calls.js' in template_content:
            print("Embedded calls script already injected")
            return True

        # Find a good place to inject our script (before closing </body> tag)
        script_injection = '''
<!-- Zulip Calls Plugin - Embedded Call Integration -->
<script>
// Load embedded calls functionality if plugin is active
if (window.location.pathname.indexOf('/') === 0) {
    fetch('/calls/script')
        .then(response => response.text())
        .then(html => {
            document.head.insertAdjacentHTML('beforeend', html);
        })
        .catch(err => console.log('Embedded calls not available:', err));
}
</script>
'''

        # Insert before closing body tag
        if '</body>' in template_content:
            template_content = template_content.replace('</body>', script_injection + '\n</body>')

            # Write back the modified template
            with open(app_template_path, 'w') as f:
                f.write(template_content)

            print("Successfully injected embedded calls script")
            return True
        else:
            print("Warning: Could not find </body> tag in template")
            return False

    except Exception as e:
        print(f"Error injecting embedded calls script: {e}")
        return False


def remove_embedded_calls_script():
    """
    Remove the embedded calls script from Zulip's main template.
    This should be called during plugin uninstallation.
    """
    try:
        # Find Zulip's main app template
        app_template_path = None
        for template_dir in settings.TEMPLATES[0]['DIRS']:
            potential_path = os.path.join(template_dir, 'zerver', 'app.html')
            if os.path.exists(potential_path):
                app_template_path = potential_path
                break

        if not app_template_path:
            print("Warning: Could not find Zulip's main app template")
            return False

        # Read the current template
        with open(app_template_path, 'r') as f:
            template_content = f.read()

        # Remove our script injection
        lines = template_content.split('\n')
        new_lines = []
        skip_next_lines = False
        skip_count = 0

        for line in lines:
            if '<!-- Zulip Calls Plugin - Embedded Call Integration -->' in line:
                skip_next_lines = True
                skip_count = 0
                continue
            elif skip_next_lines:
                skip_count += 1
                if '</script>' in line:
                    skip_next_lines = False
                continue
            else:
                new_lines.append(line)

        # Write back the modified template
        modified_content = '\n'.join(new_lines)
        with open(app_template_path, 'w') as f:
            f.write(modified_content)

        print("Successfully removed embedded calls script")
        return True

    except Exception as e:
        print(f"Error removing embedded calls script: {e}")
        return False