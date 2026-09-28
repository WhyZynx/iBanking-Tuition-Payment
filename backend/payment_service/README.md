# Payment Service

Entry point: `main:app` from the service directory.

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8003
```

This entry point and port are for running the isolated service in the combined repository. Payment workflow and database configuration remain as in the imported source.