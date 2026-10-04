"""No-data probe for the Mumbai FastAPI runtime in the existing Vercel project."""

import os
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/region_preview")
def region_preview() -> dict[str, str]:
    return {"region": os.environ.get("VERCEL_REGION", "unknown")}


@app.get("/api/region_preview/nested")
def nested_route() -> dict[str, str]:
    return {"route": "nested"}
