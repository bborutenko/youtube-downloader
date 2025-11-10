# Youtube Downloader

Compact FastAPI microservice that lets control YouTube downloads through a single, reusable interface. The service keeps cookie handling, download logic, and file cleanup in one place so the integration stays lightweight.

## Environment Variables

The service reads optional variables from `config/settings.py`. You can run it with the defaults, but you may override paths to cookie storage, download directories, or other settings by exporting the relevant variables before starting the app.

```
export YOUTUBE_COOKIES_DIR=./storage/cookies
export YOUTUBE_TMP_DIR=./tmp
uv run src/main.py
```

All environment variables are optional; the application supplies sensible defaults if you omit them.

## Usage

1. **Upload cookies**
   Call `POST /youtube/cookies` with a form field `file_name` (the name to store) and a file field `file` containing your cookies. Netscape-format exports (`cookies.txt`) are supported out of the box. Firefox `cookies.sqlite` dumps are also accepted—the service converts them automatically.

2. **Download a video**
   Use `GET /youtube/video` with query parameters:
   - `url`: the YouTube video URL.
   - `cookies_name`: the URL returned from the previous step (or the stored filename if you expose it directly).

   The service downloads the video to a temporary directory, merges audio and video, and streams the resulting MP4 back in the response.

Typical flow:

```
POST /youtube/cookies
  file_name = session_cookies.txt
  file      = @cookies.txt

GET /youtube/video?url=https://youtube.com/watch?v=dQw4w9WgXcQ&cookies_url=/youtube/cookies/session_cookies.txt
```

The response is an `video/mp4` file that you can forward or store as needed. Temporary files are cleaned up automatically after the request completes.
