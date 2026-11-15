import os
import uuid

import httpx


def test_frontend_registration_payload_matches_api():
    base = os.environ.get('OMNIVA_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    response = httpx.post(f'{base}/api/v1/auth/register', json={
        'name': 'Frontend Contract Learner',
        'email': f'qa-ui-{uuid.uuid4().hex}@example.test',
        'password': 'qa-only-safe-password-123',
    }, timeout=8)
    assert response.status_code == 201, (
        'Frontend currently posts {name,email,password}; reconcile the backend schema or the client. '
        f'Got {response.status_code}: {response.text}'
    )


def test_frontend_career_constraints_payload_matches_api():
    base = os.environ.get('OMNIVA_API_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    registered = httpx.post(f'{base}/api/v1/auth/register', json={
        'email': f'qa-career-{uuid.uuid4().hex}@example.test',
        'display_name': 'Career Contract Learner',
        'password': 'qa-only-safe-password-123',
    }, timeout=8)
    assert registered.status_code == 201, registered.text
    headers = {'Authorization': f"Bearer {registered.json()['access_token']}"}
    response = httpx.post(f'{base}/api/v1/features/career/recommendations', headers=headers, json={
        'education_level': 'not_specified',
        'interests': ['Creative problem-solving'],
        'skills': [],
        'constraints': {'goal': 'Explore accessible learning design'},
    }, timeout=8)
    assert response.status_code == 200, (
        'Frontend sends constraints as an object while backend declares list[str]. '
        f'Got {response.status_code}: {response.text}'
    )
