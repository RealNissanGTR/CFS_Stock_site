import time
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  
from fastapi import Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import jwt
import os