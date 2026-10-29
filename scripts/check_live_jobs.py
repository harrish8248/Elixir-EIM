import httpx

with httpx.Client(base_url="http://127.0.0.1:8000") as client:
    login_res = client.post("/api/v1/auth/token", json={"username": "sarah.chen@acrocorp.com", "password": "password123"})
    jobs_res = client.get("/api/v1/idp/jobs")
    items = jobs_res.json()["items"]
    first_job_id = items[0]["id"]
    job_res = client.get(f"/api/v1/idp/jobs/{first_job_id}")
    print("Job detail status:", job_res.status_code)
    job = job_res.json()
    print("Job filename:", job.get("filename"))
    print("Fields count:", len(job.get("fields", [])))
    for f in job.get("fields", [])[:5]:
        print(f"  Field: {f['field_name']} = {f['field_value']} (conf={f['confidence']})")
    print("Validation rules:", len(job.get("validation_results", [])))
