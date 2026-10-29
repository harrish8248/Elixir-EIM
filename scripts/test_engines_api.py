import urllib.request
import json

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/v1/auth/token',
    data=json.dumps({'username': 'admin@acrocorp.com', 'password': 'password123'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as resp:
    cookies = resp.headers.get('Set-Cookie')
    cookie_header = {'Cookie': cookies} if cookies else {}
    
    eng_req = urllib.request.Request('http://127.0.0.1:8000/api/v1/idp/engines/status', headers=cookie_header)
    with urllib.request.urlopen(eng_req) as eng_resp:
        body = json.loads(eng_resp.read().decode())
        print('Status code:', eng_resp.status)
        print('Installed count:', body.get('installed_count'), '/', body.get('total_engines'))
        print('Active count:', body.get('active_count'))
        for e in body.get('engines', []):
            print(f" - {e['id']}: installed={e['is_installed']}, status='{e['status']}', enabled={e['is_enabled']}")

