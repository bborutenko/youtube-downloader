from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Проверка состояния сервиса")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
