import time
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  
from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import jwt
import os

app = FastAPI()
templates = Jinja2Templates(directory="../Frontend")

@app.get("/")
def home():
    return RedirectResponse(url="/Frontend/signin", status_code=303)

@app.get("/Frontend/")
def index_redirect():
    return RedirectResponse(url="/Frontend/signin", status_code=303)

@app.get("/Frontend/login", response_class=HTMLResponse)
def login_page(request: Request):       
    context = {'request': request}
    return templates.TemplateResponse("login.html", context)
