from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Proceso vivo. No toca la BD: de eso se encarga el healthcheck de db en compose."""
    return {"status": "UP"}
