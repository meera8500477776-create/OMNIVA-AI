import json
import os

import httpx

REQUIRED = {
    '/health/live': {'get'}, '/health/ready': {'get'},
    '/api/v1/auth/register': {'post'}, '/api/v1/auth/login': {'post'},
    '/api/v1/auth/refresh': {'post'}, '/api/v1/auth/logout': {'post'},
    '/api/v1/auth/password/forgot': {'post'}, '/api/v1/auth/password/reset': {'post'},
    '/api/v1/auth/me': {'get', 'patch'},
    '/api/v1/courses': {'get'}, '/api/v1/courses/{course_id}': {'get'},
    '/api/v1/courses/{course_id}/enroll': {'post'}, '/api/v1/lessons/{lesson_id}': {'get'},
    '/api/v1/me/progress': {'get'}, '/api/v1/me/progress/{lesson_id}': {'put'},
    '/api/v1/quizzes/attempts': {'post'}, '/api/v1/me/enrollments': {'get'},
    '/api/v1/dashboard': {'get'}, '/api/v1/dashboard/analytics': {'get'},
    '/api/v1/features/career/recommendations': {'post'},
    '/api/v1/features/tutor/sessions': {'post'},
    '/api/v1/features/tutor/sessions/{session_id}/turns': {'post'},
    '/api/v1/features/voice/sessions': {'post'}, '/api/v1/features/avatar/sessions': {'post'},
    '/api/v1/features/voice/sessions/{session_id}/turns': {'post'},
    '/api/v1/features/voice/sessions/{session_id}/transcribe': {'post'},
    '/api/v1/features/voice/sessions/{session_id}/cancel': {'post'},
    '/api/v1/features/desktop/sessions': {'post'},
    '/api/v1/features/care-companion/personas': {'get'},
    '/api/v1/features/care-companion/sessions': {'post'},
    '/api/v1/features/care-companion/sessions/{session_id}/turns': {'post'},
    '/api/v1/features/email-agent/inbox': {'get'},
    '/api/v1/features/care-companion/reminders': {'get', 'post'},
    '/api/v1/features/care-companion/reminders/{reminder_id}/acknowledge': {'post'},
    '/api/v1/autopilot/plans': {'post'},
    '/api/v1/autopilot/history': {'get'},
    '/api/v1/autopilot/workflows/{workflow_id}/browser-evidence': {'get'},
}


def test_openapi_exposes_implemented_api_contracts():
    base = os.environ.get('OMNIVA_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    schema = httpx.get(f'{base}/openapi.json', timeout=8).json()
    paths = schema.get('paths', {})
    missing = {
        path: sorted(methods - {method.lower() for method in paths.get(path, {})})
        for path, methods in REQUIRED.items()
        if path not in paths or methods - {method.lower() for method in paths[path]}
    }
    assert not missing, json.dumps(missing, indent=2)


def test_openapi_does_not_disclose_secret_configuration():
    base = os.environ.get('OMNIVA_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    encoded = json.dumps(httpx.get(f'{base}/openapi.json', timeout=8).json()).lower()
    assert 'provider_api_key' not in encoded
    assert 'smtp_password' not in encoded
