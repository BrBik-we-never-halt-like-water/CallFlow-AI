"""Dev entrypoint for the CallFlow AI backend.

    python run_api.py

Reads .env, so CALLE_API_KEY and the CALLFLOW_* safety settings apply.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("callflow.api:app", host="127.0.0.1", port=8000, reload=True)
