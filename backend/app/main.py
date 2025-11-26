from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine
from .models import fire_incidents, grid, firms
from .routers import incidents as incidents_router
from .routers import risk as risk_router
from .routers import optimize as optimize_router
from .routers import chat as chat_router
from .routers import routes as routes_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SERO Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents_router.router, prefix="/incidents", tags=["incidents"])
app.include_router(risk_router.router, prefix="/risk", tags=["risk"])
app.include_router(optimize_router.router, prefix="/optimize", tags=["optimize"])
app.include_router(chat_router.router, prefix="/chat", tags=["chat"])
app.include_router(routes_router.ROUTER)

