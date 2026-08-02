
"""
Brute Force Protection Test Script
This script tests the brute force protection mechanism of the authentication endpoint.
"""
"""
import requests
import time

url = 'http://localhost:8000/api/v1/auth/login'
payload = {'email': 'oyediran.ug@atbu.edu.ng', 'password': 'ATBU2026'}

for i in range(8):
    res = requests.post(url, json=payload)
    print(f"Attempt {i+1}: Status={res.status_code} Response={res.json().get('detail', '')[:80]}")
    time.sleep(0.2)
"""
#JWT TOKEN TAMPERING TEST SCRIPT
"""
import requests
import base64
import json

# Login first
res = requests.post('http://localhost:8000/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json().get('access_token', '')
print('Original token:', token[:50], '...')

# Try to decode and tamper with the payload
parts = token.split('.')
if len(parts) == 3:
    # Decode the payload
    payload_padded = parts[1] + '=='
    payload = json.loads(base64.b64decode(payload_padded))
    print('Token payload:', payload)

    # Try to use a tampered token (change user ID)
    payload['sub'] = 'fake-user-id-12345'
    import json
    fake_payload = base64.b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip('=')
    fake_token = parts[0] + '.' + fake_payload + '.' + parts[2]

    # Try to use the tampered token
    res2 = requests.get(
        'http://localhost:8000/api/v1/auth/me',
        headers={'Authorization': f'Bearer {fake_token}'}
    )
    print('Tampered token result:', res2.status_code, res2.json())
"""
#TOKEN REUSE AFTER LOGOUT TEST SCRIPT
"""
import requests

BASE = 'http://localhost:8000'

# Login
res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
print('Logged in, token:', token[:30], '...')

headers = {'Authorization': f'Bearer {token}'}

# Verify token works
res = requests.get(f'{BASE}/api/v1/auth/me', headers=headers)
print('Before logout:', res.status_code)

# Logout
res = requests.post(f'{BASE}/api/v1/auth/logout', headers=headers)
print('Logout:', res.status_code, res.json())

# Try to reuse the token after logout
res = requests.get(f'{BASE}/api/v1/auth/me', headers=headers)
print('After logout (should be 401):', res.status_code, res.json())
"""

"""
#Large Payload Test Script
import requests

# Try to send extremely large payload
large_string = 'A' * 100000

res = requests.post('http://localhost:8000/api/v1/auth/register', json={
    'email': 'test@test.com',
    'password': 'Passw0rd1',
    'full_name': large_string,
    'country': 'NG'
})
print('Large payload result:', res.status_code)
print('Response:', str(res.json())[:200])
"""
"""
#Negative Deposit and Withdrawal Test Script
import requests

BASE = 'http://localhost:8000'

# Login first
res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try negative deposit
res = requests.post(f'{BASE}/api/v1/wallet/deposit',
    json={'amount': -999999, 'description': 'hack'},
    headers=headers
)
print('Negative deposit:', res.status_code, res.json())

# Try zero amount withdrawal
res = requests.post(f'{BASE}/api/v1/withdraw/initiate',
    json={
        'amount': 0,
        'bank_details': {
            'bank_name': 'GTBank',
            'account_number': '0123456789',
            'account_name': 'Test User',
            'bank_code': '058',
            'destination_country': 'NG',
            'destination_currency': 'NGN'
        }
    },
    headers=headers
)
print('Zero withdrawal:', res.status_code, res.json())

# Try extremely large amount
res = requests.post(f'{BASE}/api/v1/wallet/deposit',
    json={'amount': 999999999999, 'description': 'hack'},
    headers=headers
)
print('Huge deposit:', res.status_code, res.json())

"""

#Invalid Currency Test Script
"""
import requests

BASE = 'http://localhost:8000'
res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try fake currency
res = requests.post(f'{BASE}/api/v1/fx/quote',
    json={'from_amount': 100, 'to_currency': 'FAKE'},
    headers=headers
)
print('Fake currency:', res.status_code, res.json())

# Try empty currency
res = requests.post(f'{BASE}/api/v1/fx/quote',
    json={'from_amount': 100, 'to_currency': ''},
    headers=headers
)
print('Empty currency:', res.status_code, res.json())

"""
#Authorization attacks

#Access others data
"""
import requests

BASE = 'http://localhost:8000'

# Login as user 1
res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try to access a random withdrawal reference that belongs to another user
fake_ref = 'WDR-AAAAAAAAAAAAAAAA'
res = requests.get(
    f'{BASE}/api/v1/withdraw/{fake_ref}',
    headers=headers
)
print('Access other user withdrawal:', res.status_code, res.json())

# Try to access admin endpoints without admin key
res = requests.get(f'{BASE}/api/v1/admin/stats')
print('Admin without key:', res.status_code)

res = requests.get(
    f'{BASE}/api/v1/admin/stats',
    headers={'x-admin-key': 'wrongkey'}
)
print('Admin with wrong key:', res.status_code)
"""

# IDOR (Insecure Direct Object Reference)
"""
import requests
import uuid

BASE = 'http://localhost:8000'

res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try to access a random UUID withdrawal
random_id = str(uuid.uuid4())
res = requests.get(
    f'{BASE}/api/v1/withdraw/{random_id}',
    headers=headers
)
print('Random UUID access:', res.status_code)

# Try path traversal
res = requests.get(
    f'{BASE}/api/v1/withdraw/../admin/stats',
    headers=headers
)
print('Path traversal:', res.status_code)

#KYC Bypass Test Script
"""
"""
import requests

BASE = 'http://localhost:8000'

# Login with a non-KYC user
res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try withdrawal above KYC limit without KYC
res = requests.post(f'{BASE}/api/v1/withdraw/initiate',
    json={
        'amount': 1000,
        'bank_details': {
            'bank_name': 'GTBank',
            'account_number': '0123456789',
            'account_name': 'Test User',
            'bank_code': '058',
            'destination_country': 'NG',
            'destination_currency': 'NGN'
        }
    },
    headers=headers
)
print('KYC bypass attempt:', res.status_code)
print('Response:', res.json().get('detail', '')[:200])
"""
"""
#ADVANCED ATTACKS
#Rate Limit Bypass Attempt Test Script

import requests
import time

BASE = 'http://localhost:8000'

print('Testing rate limit with different headers...')

for i in range(10):
    # Try to bypass rate limit by spoofing IP headers
    res = requests.post(f'{BASE}/api/v1/auth/login',
        json={'email': f'fake{i}@test.com', 'password': 'wrong'},
        headers={
            'X-Forwarded-For': f'192.168.{i}.{i}',
            'X-Real-IP': f'10.0.{i}.{i}'
        }
    )
    print(f'Attempt {i+1}: {res.status_code}')
    time.sleep(0.1)
"""
#Mass Assignment Test Script
"""
import requests

BASE = 'http://localhost:8000'

res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Try to set is_kyc_verified or is_active via profile update
res = requests.put(f'{BASE}/api/v1/users/profile',
    json={
        'full_name': 'Hacker',
        'is_kyc_verified': True,
        'is_active': True,
        'is_admin': True,
        'balance': 999999
    },
    headers=headers
)
print('Mass assignment result:', res.status_code)
print('Response:', res.json())

# Verify KYC was not set
res = requests.get(f'{BASE}/api/v1/auth/me', headers=headers)
user = res.json()
print('KYC after attack:', user.get('is_kyc_verified'))
"""
#DOUBLE SPENDING / REPLAY ATTACK TEST SCRIPT
"""
import requests
import threading

BASE = 'http://localhost:8000'

res = requests.post(f'{BASE}/api/v1/auth/login', json={
    'email': 'oyediran.ug@atbu.edu.ng',
    'password': 'ATBU2026'
})
token = res.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# First deposit a small amount
requests.post(f'{BASE}/api/v1/wallet/deposit',
    json={'amount': 100, 'description': 'Test'},
    headers=headers
)

# Check balance
res = requests.get(f'{BASE}/api/v1/wallet/balance', headers=headers)
balance = float(res.json()['balance'])
print(f"Balance before attack: \${balance}")

# Try to withdraw the same amount simultaneously (double spend)
results = []
def withdraw():
    res = requests.post(f'{BASE}/api/v1/withdraw/initiate',
        json={
            'amount': balance,
            'bank_details': {
                'bank_name': 'GTBank',
                'account_number': '0123456789',
                'account_name': 'Test User',
                'bank_code': '058',
                'destination_country': 'NG',
                'destination_currency': 'NGN'
            }
        },
        headers=headers
    )
    results.append(res.status_code)

# Fire 3 simultaneous withdrawal requests
threads = [threading.Thread(target=withdraw) for _ in range(3)]
for t in threads: t.start()
for t in threads: t.join()

print('Simultaneous withdrawal results:', results)

# Check final balance
res = requests.get(f'{BASE}/api/v1/wallet/balance', headers=headers)
print(f"Balance after attack: ${res.json()['balance']}")
print('Only one should have succeeded, balance should not be negative')
"""

#SECURITY HEADERS TEST SCRIPT
"""
import requests

BASE = 'http://localhost:8000'

res = requests.get(f'{BASE}/health')
headers = res.headers

security_headers = [
    'X-Content-Type-Options',
    'X-Frame-Options',
    'Strict-Transport-Security',
    'X-XSS-Protection',
    'Referrer-Policy',
    'Permissions-Policy',
    'X-Request-ID',
]

print('=== Security Headers Check ===')
all_present = True
for h in security_headers:
    value = headers.get(h, 'MISSING')
    status = 'PASS' if value != 'MISSING' else 'FAIL'
    if value == 'MISSING':
        all_present = False
    print(f'{status}: {h} = {value[:60]}')

print()
print('Server header:', headers.get('Server', 'Not set'))
print()
if all_present:
    print('ALL SECURITY HEADERS PRESENT')
else:
    print('SOME HEADERS MISSING - review middleware')
"""

"""
#WEBHOOK SIGNATURE BYPASS TEST SCRIPT

import requests

BASE = 'http://localhost:8000'

# Try to fake a webhook from Flutterwave without valid signature
fake_payload = {
    'event': 'transfer.completed',
    'data': {
        'id': 99999,
        'reference': 'WDR-FAKEREF12345678',
        'status': 'SUCCESSFUL'
    }
}

# Without signature
res = requests.post(
    f'{BASE}/api/v1/webhooks/flutterwave',
    json=fake_payload
)
print('Fake webhook without sig:', res.status_code, res.json())

# With wrong signature
res = requests.post(
    f'{BASE}/api/v1/webhooks/flutterwave',
    json=fake_payload,
    headers={'verif-hash': 'wrongsignature123'}
)
print('Fake webhook with wrong sig:', res.status_code)
"""
"""
import os
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import httpx
except ImportError:
    print("httpx not installed. Install it with: pip install httpx")
    httpx = None

if load_dotenv is not None:
    load_dotenv()
else:
    print("python-dotenv not installed; using environment variables directly")

SECRET_KEY = os.getenv('FLUTTERWAVE_SECRET_KEY', '')
print('Key starts with:', SECRET_KEY[:15], '...')
print('Key length:', len(SECRET_KEY))

response = httpx.post(
    'https://api.flutterwave.com/v3/accounts/resolve',
    headers={
        'Authorization': f'Bearer {SECRET_KEY}',
        'Content-Type': 'application/json'
    },
    json={
        'account_number': '0009655243',
        'account_bank': '301'
    },
    timeout=15.0
)
print('Status:', response.status_code)
print('Response:', response.json())
"""


"""
import httpx, os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('PAYSTACK_SECRET_KEY', '')
r = httpx.get(
    'https://api.paystack.co/bank',
    headers={'Authorization': f'Bearer {key}'},
    params={'country': 'nigeria', 'perPage': 200},
    timeout=15.0
)
data = r.json()
banks = data.get('data', [])
active = [b for b in banks if b.get('active')]
print(f'Total banks: {len(banks)}, Active: {len(active)}')
print('First 5:', [(b["name"], b["code"]) for b in active[:5]])
print('Kuda:', [(b["name"], b["code"]) for b in active if 'kuda' in b["name"].lower()])
print('Opay:', [(b["name"], b["code"]) for b in active if 'opay' in b["name"].lower()])
print('Moniepoint:', [(b["name"], b["code"]) for b in active if 'moniepoint' in b["name"].lower()])
"""
"""
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('PAYSTACK_SECRET_KEY', '')
print('Key starts with:', key[:15])
print('Key length:', len(key))
print('Is live key:', key.startswith('sk_live_'))
print()

# Test 1 — Check key validity
print('--- Test 1: Key Validity ---')
r = httpx.get(
    'https://api.paystack.co/bank',
    headers={'Authorization': f'Bearer {key}'},
    params={'country': 'nigeria', 'perPage': 5},
    timeout=10.0
)
data = r.json()
print('Status:', r.status_code)
print('API Status:', data.get('status'))
print('Message:', data.get('message'))
if data.get('status'):
    banks = data.get('data', [])
    print(f'Banks returned: {len(banks)}')
    for b in banks[:3]:
        print(f"  - {b['name']} (code: {b['code']})")
print()

# Test 2 — Get all active banks
print('--- Test 2: Full Bank List ---')
r2 = httpx.get(
    'https://api.paystack.co/bank',
    headers={'Authorization': f'Bearer {key}'},
    params={'country': 'nigeria', 'perPage': 200, 'use_cursor': False},
    timeout=15.0
)
data2 = r2.json()
if data2.get('status'):
    all_banks = data2.get('data', [])
    active = [b for b in all_banks if b.get('active', True)]
    print(f'Total banks: {len(all_banks)}')
    print(f'Active banks: {len(active)}')
    print()
    
    # Find key banks
    targets = ['kuda', 'opay', 'moniepoint', 'palmpay', 'guaranty', 'zenith', 'access', 'uba', 'first bank']
    print('Key banks found:')
    for target in targets:
        found = [b for b in active if target.lower() in b.get('name', '').lower()]
        for b in found[:1]:
            print(f"  {b['name']} -> code: {b['code']}")
print()

# Test 3 — Account verification with a real account
print('--- Test 3: Account Verification ---')
TEST_ACCOUNT = '0123456789'  # Replace with your real GTBank account
TEST_BANK_CODE = '058'       # GTBank
r3 = httpx.get(
    'https://api.paystack.co/bank/resolve',
    headers={'Authorization': f'Bearer {key}'},
    params={
        'account_number': TEST_ACCOUNT,
        'bank_code': TEST_BANK_CODE
    },
    timeout=15.0
)
data3 = r3.json()
print('Status:', r3.status_code)
print('Response:', data3)
print()

# Test 4 — Check transfer capability
print('--- Test 4: Transfer Capability ---')
r4 = httpx.get(
    'https://api.paystack.co/balance',
    headers={'Authorization': f'Bearer {key}'},
    timeout=10.0
)
data4 = r4.json()
print('Balance check status:', r4.status_code)
print('Response:', data4)
"""
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("PAYSTACK_SECRET_KEY", "")

# ============================================================
# Replace these with YOUR real Nigerian bank account details
# ============================================================
YOUR_ACCOUNT_NUMBER = "3022434615"   # Replace with your real account number
YOUR_BANK_CODE = "11"               # 058 = GTBank, 057 = Zenith, 044 = Access
# ============================================================

print(f"Testing with account: {3022434615} at bank code: {11}")

r = httpx.get(
    "https://api.paystack.co/bank/resolve",
    headers={"Authorization": f"Bearer {key}"},
    params={
        "account_number": 3022434615,
        "bank_code": 11
    },
    timeout=15.0
)
print("Status:", r.status_code)
print("Response:", r.json())
