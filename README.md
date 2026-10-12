# BetPlay Password Change API

API para cambiar contraseñas de cuentas BetPlay mediante requests HTTP.

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

### Iniciar la API:
```bash
python betplay_password_api.py
```

La API estará disponible en `http://localhost:8000`

### Documentación automática:
Abre tu navegador en: **http://localhost:8000/docs**

## Endpoints

### POST /change-password

Cambia la contraseña de una cuenta BetPlay.

**Body:**
```json
{
  "username": "22378522",
  "current_password": "contraseña_actual",
  "new_password": "nueva_contraseña"
}
```

**Respuesta exitosa:**
```json
{
  "success": true,
  "message": "Contraseña cambiada correctamente",
  "status_code": 200,
  "profile": {
    "username": "22378522",
    "name": "NOMBRE APELLIDO",
    "email": "email@ejemplo.com",
    "document": "22378522"
  },
  "balance": {
    "totalBalance": 16.5,
    "realBalance": 16.5,
    "bonusBalance": 0
  }
}
```

## Ejemplo con Python

```python
import requests

response = requests.post(
    "http://localhost:8000/change-password",
    json={
        "username": "22378522",
        "current_password": "contraseña_actual",
        "new_password": "nueva_contraseña"
    }
)
print(response.json())
```

## Ejemplo con cURL

```bash
curl -X POST http://localhost:8000/change-password \
  -H "Content-Type: application/json" \
  -d '{"username":"22378522","current_password":"actual","new_password":"nueva"}'
```

## Despliegue

Para desplegar en un servidor:

```bash
uvicorn betplay_password_api:app --host 0.0.0.0 --port 8000
```

## Archivos

- `betplay_password_api.py` - API principal
- `ejemplo_uso_api.py` - Ejemplo de uso con Python
- `requirements.txt` - Dependencias

## Notas

- La API usa `curl_cffi` para evitar bloqueos de Cloudflare
- Requiere conexión a internet
- Los endpoints de BetPlay pueden cambiar sin previo aviso
