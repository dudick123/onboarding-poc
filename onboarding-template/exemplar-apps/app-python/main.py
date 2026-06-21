from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Hello World API", version="1.0.0")


class HealthResponse(BaseModel):
    status: str


class HelloResponse(BaseModel):
    message: str


@app.get("/", response_model=HelloResponse)
async def hello() -> HelloResponse:
    return HelloResponse(message="Hello, World!")


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
