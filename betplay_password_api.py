"""
API para cambio de contraseña en BetPlay
FastAPI con documentación automática en /docs
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional
from curl_cffi import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn


# ---------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------
BASE_URL     = "https://betplay.com.co"
TOKEN_WINDOW = 90
JWT_SECRET   = "kw4he!je!4Pf#[["
BPC_KEY      = "191BCCEB25E8718E8BB58C21B63B9"
VERSION      = "4.0.71"

# Proxy residencial (2captcha) - variables de entorno o defaults
PROXY_USER = os.environ.get("PROXY_USER", "u1ebdced056e605cf-zone-custom-region-co")
PROXY_PASS = os.environ.get("PROXY_PASS", "u1ebdced056e605cf")
PROXY_DNS  = os.environ.get("PROXY_DNS", "na.proxy.2captcha.com:2334")

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
    except Exception as e:
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
    version="1.0.0"
)


@app.post("/change-password", response_model=ChangePasswordResponse)
async def change_password(request: ChangePasswordRequest):
    """
    Cambia la contraseña de una cuenta BetPlay
    
    - **username**: Documento del usuario (ej: "22378522")
    - **current_password**: Contraseña actual
    - **new_password**: Nueva contraseña
    """
    result = change_password_api(
        request.username,
        request.current_password,
        request.new_password
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result["message"]
        )
    
    return result


@app.get("/")
async def root():
    return {
        "message": "BetPlay Password Change API",
        "docs": "/docs",
        "endpoints": {
            "POST /change-password": "Cambiar contraseña de cuenta"
        }
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
