"""
Ejemplo de uso de la API de BetPlay
"""

import requests

API_URL = "http://localhost:8000"


def cambiar_contrasena(username: str, current_password: str, new_password: str):
    """Cambia la contraseña de una cuenta BetPlay"""
    
    response = requests.post(
        f"{API_URL}/change-password",
        json={
            "username": username,
            "current_password": current_password,
            "new_password": new_password
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Contraseña cambiada exitosamente")
        print(f"  Usuario: {data['profile']['username']}")
        print(f"  Nombre: {data['profile']['name']}")
        print(f"  Email: {data['profile']['email']}")
        print(f"  Balance: {data['balance'].get('totalBalance', 0)}")
        return data
    else:
        print(f"✗ Error: {response.status_code}")
        print(f"  {response.json().get('detail', 'Error desconocido')}")
        return None


if __name__ == "__main__":
    # Ejemplo de uso
    cambiar_contrasena(
        username="22378522",
        current_password="Diosfiel1$",
        new_password="NuevaContraseña123@"
    )
