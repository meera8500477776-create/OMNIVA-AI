import json
import os
import urllib.error
import urllib.request
from pathlib import Path

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
    '/api/v1/features/desktop/sessions': {'post'},
}


def main() -> None:
    base = os.environ.get('OMNIVA_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    request = urllib.request.Request(base + '/openapi.json', headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            schema = json.load(response)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f'BLOCKED: API OpenAPI unavailable at {base}: {exc}') from exc
    paths = schema.get('paths', {})
    missing = {
        path: sorted(methods - {method.lower() for method in paths.get(path, {})})
        for path, methods in REQUIRED.items()
        if path not in paths or methods - {method.lower() for method in paths[path]}
    }
    if missing:
        raise SystemExit('FAIL: required implemented contract paths/methods absent: ' + json.dumps(missing))
    output = Path(os.environ.get('OMNIVA_OPENAPI_OUTPUT', 'work/qa-results/openapi.json'))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2) + '\n', encoding='utf-8')
    print(f'PASS: OpenAPI contains {len(REQUIRED)} required health/auth/LMS/feature paths.')
    for path in paths:
        if any(word in path.lower() for word in ('email', 'companion', 'care')):
            print('INFO: optional future path:', path)


if __name__ == '__main__':
    main()
