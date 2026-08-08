
import requests

res = requests.post(
    'https://payflow-api-u0a5.onrender.com/api/v1/auth/register',
    json={
        'email': 'testuser@gmail.com',
        'password': 'TestPass1',
        'full_name': 'Test User',
        'country': 'NG'
    },
    headers={
        'Content-Type': 'application/json',
        'Origin': 'https://payflow-frontend-jxij.vercel.app'
    }
)
print('Status:', res.status_code)
print('Response:', res.json())
