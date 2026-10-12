
import hashlib
import hmac
import secrets

ITERACIONES = 260_000


def generar_hash(password):
    
    sal = secrets.token_hex(16)  

    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),  
        sal.encode("utf-8"),
        ITERACIONES,
    )
    hash_hex = hash_bytes.hex()

    return f"pbkdf2_sha256${ITERACIONES}${sal}${hash_hex}"


def verificar_password(password, hash_guardado):
    
    try:
        algoritmo, iteraciones_texto, sal, hash_esperado = hash_guardado.split("$")
    except ValueError:
        
        return False

    iteraciones = int(iteraciones_texto)

    hash_calculado = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        sal.encode("utf-8"),
        iteraciones,
    ).hex()

    return hmac.compare_digest(hash_calculado, hash_esperado)


# Sin 0/O, 1/I/L para que el codigo se pueda copiar a mano sin confusiones.
_ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_codigo_recuperacion():
    """
    Codigo aleatorio de 12 caracteres en grupos de 4 (ej. 'K7QM-3XRA-9TPW').
    Solo se muestra una vez al usuario; en la base se guarda su hash.
    """
    caracteres = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(12))
    return "-".join(caracteres[i:i + 4] for i in range(0, 12, 4))


def normalizar_codigo(codigo):
    """'k7qm 3xra-9tpw' -> 'K7QM3XRA9TPW' (se hashea y compara sin guiones ni espacios)."""
    return "".join(c for c in (codigo or "").upper() if c.isalnum())


if __name__ == "__main__":

    prueba_hash = generar_hash("MiClaveSegura123")
    print("Hash generado:", prueba_hash)

    print("Verificar con clave correcta:", verificar_password("MiClaveSegura123", prueba_hash))
    print("Verificar con clave incorrecta:", verificar_password("ClaveEquivocada", prueba_hash))
