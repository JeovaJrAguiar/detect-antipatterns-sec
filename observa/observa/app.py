import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from observa.api.router import router as api_router
from observa.framework.orchestrator import global_orchestrator as orchestrator
from observa.security.cors import parse_allowed_origins
from observa.security.observability import (
    RequestLoggingMiddleware,
    configure_structured_logging,
)
from observa.security.rate_limit import RateLimitMiddleware

configure_structured_logging()
orchestrator.load()

fastapi_app = FastAPI(title="Observa API + Frontend")
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(os.getenv("OBSERVA_CORS_ORIGINS", "")),
    allow_methods=["*"],
    allow_headers=["*"],
)
fastapi_app.add_middleware(RateLimitMiddleware)
fastapi_app.include_router(api_router)
fastapi_app.mount("/static", StaticFiles(directory="observa/static"), name="static")
templates = Jinja2Templates(directory="observa/templates")

@fastapi_app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request}
    )


app = RequestLoggingMiddleware(fastapi_app)