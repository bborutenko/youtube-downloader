import logging
import shutil
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

_YTDL_OPTS = {
    "format": "bv*+ba/b",
    "merge_output_format": "mp4",
    "quiet": True,
    "noplaylist": True,
}

logger = logging.getLogger(__name__)


class CookieService:
    @staticmethod
    def _convert_firefox_sqlite_to_netscape(content: bytes) -> bytes:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            temp_path = Path(tmp.name)

        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            tables = {
                row[0]
                for row in cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table';"
                )
            }

            if "moz_cookies" not in tables:
                raise ValueError(
                    "SQLite cookies file is not in the expected Firefox format."
                )

            rows = cursor.execute(
                "SELECT host, path, isSecure, expiry, name, value, "
                "COALESCE(isHttpOnly, 0) FROM moz_cookies;"
            ).fetchall()
        except sqlite3.Error as exc:
            raise ValueError("Не удалось прочитать cookies.sqlite файл.") from exc
        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass
            temp_path.unlink(missing_ok=True)

        lines = [
            "# Netscape HTTP Cookie File",
            "# Converted from Firefox cookies.sqlite",
        ]

        for host, path, is_secure, expiry, name, value, is_http_only in rows:
            domain = host or ""
            bare_domain = domain
            if is_http_only:
                domain = f"#HttpOnly_{domain}"
            if bare_domain.startswith("."):
                include_subdomains = "TRUE"
            else:
                include_subdomains = "FALSE"
            secure_flag = "TRUE" if is_secure else "FALSE"
            expiry = str(int(expiry or 0))
            name = name or ""
            value = value or ""
            path = path or "/"

            lines.append(
                "\t".join(
                    [
                        domain,
                        include_subdomains,
                        path,
                        secure_flag,
                        expiry,
                        name,
                        value,
                    ]
                )
            )

        return ("\n".join(lines) + "\n").encode("utf-8")

    @classmethod
    def _ensure_netscape_cookie_content(cls, content: bytes) -> bytes:
        if content.startswith(b"SQLite format 3"):
            return cls._convert_firefox_sqlite_to_netscape(content)

        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "Cookies file must be UTF-8 text (Netscape format)."
            ) from exc

        if "Netscape HTTP Cookie File" not in decoded:
            raise ValueError(
                "Cookies file must contain the 'Netscape HTTP Cookie File' header."
            )

        return content

    @classmethod
    def resolve_cookies_reference(
        cls, cookies_reference: str | None, cookies_dir: Path
    ) -> Path | None:
        if not cookies_reference:
            logger.debug("No cookies reference provided; skipping cookies usage.")
            return None

        parsed = urlparse(cookies_reference)
        file_name = Path(parsed.path).name
        if not file_name:
            logger.warning("Invalid cookies reference %s", cookies_reference)
            raise ValueError("Некорректный URL cookies")

        candidate_path = cookies_dir.expanduser() / file_name
        if not candidate_path.exists():
            logger.warning(
                "Cookies file %s derived from %s not found",
                candidate_path,
                cookies_reference,
            )
            raise FileNotFoundError(f"Cookies file not found: {candidate_path}")

        logger.info(
            "Resolved cookies file %s from reference %s",
            candidate_path,
            cookies_reference,
        )
        return candidate_path

    @classmethod
    def resolve_cookies_path(cls, cookies_path: str | None) -> Path | None:
        if not cookies_path:
            logger.debug("No cookies path provided; skipping cookies usage.")
            return None

        path = Path(cookies_path).expanduser()
        if not path.exists():
            logger.warning("Cookies file %s does not exist", path)
            raise FileNotFoundError(f"Cookies file not found: {path}")

        logger.info("Using cookies file %s", path)
        return path

    @classmethod
    def save_cookies_file(cls, destination: Path, content: bytes) -> Path:
        destination = destination.expanduser()
        logger.info("Saving cookies file to %s", destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp_path = destination.with_suffix(destination.suffix + ".tmp")

        processed_content = cls._ensure_netscape_cookie_content(content)

        try:
            temp_path.write_bytes(processed_content)
            temp_path.replace(destination)
        except Exception:
            logger.exception("Failed to save cookies file to %s", destination)
            raise

        logger.info("Cookies file saved to %s", destination)
        return destination


class YoutubeService:
    @classmethod
    def download_video(
        cls,
        url: str,
        target_dir: Path,
        cookies_path: str | None = None,
    ) -> Path:
        opts = {**_YTDL_OPTS, "outtmpl": str(target_dir / "%(title)s.%(ext)s")}
        cookie_file: Path | None = None

        try:
            cookie_file = CookieService.resolve_cookies_path(cookies_path)
        except FileNotFoundError:
            logger.warning("Proceeding without cookies; file %s missing", cookies_path)

        if cookie_file:
            opts["cookiefile"] = str(cookie_file)

        logger.info("Downloading video from %s into %s", url, target_dir)
        file_path: Path | None = None

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")
        except Exception:
            logger.exception("Failed to download video from %s", url)
            raise

        logger.info("Video downloaded to %s", file_path)
        return file_path

    @classmethod
    def cleanup_download(cls, temp_dir: Path) -> None:
        logger.info("Cleaning up temporary directory %s", temp_dir)
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            logger.exception("Failed to clean up directory %s", temp_dir)
