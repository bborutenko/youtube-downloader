import asyncio
import logging
import tempfile
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import HttpUrl

from config.settings import settings
from youtube.service import CookieService, YoutubeService

router = APIRouter(prefix="/youtube", tags=["Youtube"])
logger = logging.getLogger(__name__)


@router.get("/video", summary="Скачать и вернуть видео")
async def download_video_by_url(
    background_tasks: BackgroundTasks,
    url: HttpUrl = Query(..., description="Ссылка на YouTube-видео"),
    cookies_name: str = Query(
        None,
        description="Название сохранённого cookies-файла, сохраненного в POST /cookies",
    ),
):
    """Stream the requested YouTube video as an MP4 file.

    Returns:
        FileResponse: Serves the merged MP4 with HTTP 200 on success.

    Raises:
        HTTPException: 400 if the provided cookies reference is malformed.
        HTTPException: 404 if the referenced cookies file does not exist.
        HTTPException: Propagates other failures (e.g., yt-dlp errors) as 500.
    """
    logger.info("Received download request for %s", url)
    temp_dir = Path(tempfile.mkdtemp(prefix="yt-video-"))

    cookies_dir = Path(settings.YOUTUBE_COOKIES_DIR).expanduser()
    try:
        cookies_file = CookieService.resolve_cookies_reference(
            cookies_name, cookies_dir
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cookies-файл по указанному URL не найден",
        ) from exc

    cookies_path = str(cookies_file)

    try:
        file_path = await asyncio.to_thread(
            YoutubeService.download_video,
            str(url),
            temp_dir,
            cookies_path,
        )
    except Exception:
        logger.exception("Failed to download video for %s", url)
        YoutubeService.cleanup_download(temp_dir)
        raise

    logger.info("Serving video %s for %s", file_path, url)
    background_tasks.add_task(YoutubeService.cleanup_download, temp_dir)
    return FileResponse(
        file_path,
        filename=file_path.name,
        media_type="video/mp4",
        background=background_tasks,
    )


@router.post(
    "/cookies",
    summary="Загрузить cookies-файл",
    status_code=status.HTTP_201_CREATED,
)
async def upload_cookies_file(
    request: Request,
    file_name: str = Form(..., description="Название cookies-файла"),
    file: UploadFile = File(..., description="Cookies в формате Netscape"),
):
    """Persist an uploaded cookies file and return its download URL.

    Returns:
        dict: JSON payload with the stored cookies URL (HTTP 201).

    Raises:
        HTTPException: 400 if the filename/content is invalid or the file fails validation.
        HTTPException: 500 if the file cannot be saved to disk.
    """
    sanitized_name = Path(file_name).name
    if not sanitized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название файла не может быть пустым",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл cookies пуст",
        )

    destination_dir = Path(settings.YOUTUBE_COOKIES_DIR).expanduser()
    destination_path = destination_dir / sanitized_name

    try:
        saved_path = CookieService.save_cookies_file(destination_path, content)
    except ValueError as exc:
        logger.warning("Invalid cookies file %s: %s", destination_path, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Failed to save cookies file %s", destination_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось сохранить cookies",
        )

    logger.info("Cookies file stored at %s", saved_path)

    cookie_path = request.url.path.rstrip("/") + f"/{sanitized_name}"
    return {"name": f"{cookie_path}"}
