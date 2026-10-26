from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173"
                            ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MessageRequest(BaseModel):
    message: str

@app.get("/")
def home():
    return {"message": "Welcome to DocMind!"}

@app.get("/api/message")
def get_message():
    return {"message": "Hello from the DocMind backend!"}

@app.post("/api/message")
def send_message(request: MessageRequest):
    return {"reply": f"You said: {request.message}"}
