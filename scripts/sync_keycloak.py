import httpx

res = httpx.post('http://127.0.0.1:8080/realms/master/protocol/openid-connect/token', data={
    'client_id': 'admin-cli',
    'grant_type': 'password',
    'username': 'admin',
    'password': 'admin_secure_pass'
})
admin_token = res.json()['access_token']
headers = {'Authorization': f'Bearer {admin_token}'}

roles_res = httpx.get('http://127.0.0.1:8080/admin/realms/elixir/roles', headers=headers)
role_map = {r['name']: r for r in roles_res.json()}

users_to_ensure = [
    {
        'username': 'sarah.chen',
        'email': 'sarah.chen@acrocorp.com',
        'firstName': 'Sarah',
        'lastName': 'Chen',
        'roles': ['RecordsManager', 'Auditor', 'TenantAdmin']
    },
    {
        'username': 'raj.patel',
        'email': 'raj.patel@acrocorp.com',
        'firstName': 'Raj',
        'lastName': 'Patel',
        'roles': ['KnowledgeWorker']
    },
    {
        'username': 'maria.santos',
        'email': 'maria.santos@acrocorp.com',
        'firstName': 'Maria',
        'lastName': 'Santos',
        'roles': ['KnowledgeWorker']
    },
    {
        'username': 'alex.auditor',
        'email': 'alex.auditor@acrocorp.com',
        'firstName': 'Alex',
        'lastName': 'Auditor',
        'roles': ['Auditor']
    },
    {
        'username': 'admin',
        'email': 'admin@acrocorp.com',
        'firstName': 'System',
        'lastName': 'Admin',
        'roles': ['GlobalAdmin', 'TenantAdmin']
    }
]

existing_users = httpx.get('http://127.0.0.1:8080/admin/realms/elixir/users', headers=headers).json()
existing_map = {u.get('email'): u for u in existing_users if 'email' in u}

for u_def in users_to_ensure:
    email = u_def['email']
    user_id = None
    if email in existing_map:
        user_id = existing_map[email]['id']
        httpx.put(f"http://127.0.0.1:8080/admin/realms/elixir/users/{user_id}", headers=headers, json={
            'username': u_def['username'],
            'email': email,
            'firstName': u_def['firstName'],
            'lastName': u_def['lastName'],
            'enabled': True,
            'emailVerified': True
        })
    else:
        create_res = httpx.post("http://127.0.0.1:8080/admin/realms/elixir/users", headers=headers, json={
            'username': u_def['username'],
            'email': email,
            'firstName': u_def['firstName'],
            'lastName': u_def['lastName'],
            'enabled': True,
            'emailVerified': True
        })
        user_id = create_res.headers.get('Location', '').split('/')[-1]
        if not user_id:
            u_lookup = httpx.get(f"http://127.0.0.1:8080/admin/realms/elixir/users?username={u_def['username']}", headers=headers).json()
            user_id = u_lookup[0]['id']

    # Set password to password123
    httpx.put(f"http://127.0.0.1:8080/admin/realms/elixir/users/{user_id}/reset-password", headers=headers, json={
        'type': 'password',
        'value': 'password123',
        'temporary': False
    })
    
    # Assign roles
    user_roles = [role_map[r] for r in u_def['roles'] if r in role_map]
    if user_roles:
        httpx.post(f"http://127.0.0.1:8080/admin/realms/elixir/users/{user_id}/role-mappings/realm", headers=headers, json=user_roles)

print('SUCCESS')

