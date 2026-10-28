"""HU-NOT-11: alta de API Key por rol. La llave se muestra una sola vez.

Uso: python scripts/crear_api_key.py <inventario|fabricacion|notificaciones>
"""

import sys

from app.domain.autenticacion import ServicioAutenticacion
from app.domain.errores import ErrorDominio
from app.infrastructure.db import transaccion
from app.infrastructure.repositories import ApiKeyRepo


def main(rol: str) -> int:
    try:
        with transaccion() as session:
            id_, llave = ServicioAutenticacion(ApiKeyRepo(session)).crear_llave(rol)
    except ErrorDominio as e:
        print(e.mensaje, file=sys.stderr)
        return 1
    print(f"id: {id_}\nrol: {rol}\nllave: {llave}\nGuárdala: no se vuelve a mostrar.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/crear_api_key.py <rol>")
    sys.exit(main(sys.argv[1]))
