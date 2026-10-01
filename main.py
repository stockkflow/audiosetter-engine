import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import static_ffmpeg

try:
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"FFmpeg yükleme uyarısı: {e}")

app = FastAPI(title="AudioSetter YouTube Engine")

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIES_FILE = "/tmp/youtube_cookies.txt"


def setup_cookies():
    cookie_content = os.environ.get("YOUTUBE_COOKIES", "").strip()
    if not cookie_content:
        return None

    cleaned_content = cookie_content.replace("\\n", "\n").replace("\\t", "\t")
    with open(COOKIES_FILE, "w", encoding="utf-8") as f:
        f.write(cleaned_content)
    return COOKIES_FILE


setup_cookies()


class FetchRequest(BaseModel):
    url: str


@app.post("/extract-audio")
def extract_audio(req: FetchRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Geçersiz URL")

    file_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": False,
        "nocheckcertificate": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                # Çerezlerle (cookie) çalışan mobil web ve web istemcileri
                "player_client": ["mweb", "web"],
            }
        },
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    }

    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        ydl_opts["cookiefile"] = COOKIES_FILE

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "AudioSetter Track")

            final_filename = None
            for f in os.listdir(DOWNLOAD_DIR):
                if f.startswith(file_id):
                    final_filename = f
                    break

            if not final_filename:
                raise HTTPException(
                    status_code=500, detail="Ses dosyası dizine kaydedilemedi."
                )

            return {
                "status": "success",
                "title": title,
                "download_url": f"/download/{final_filename}",
            }
    except Exception as e:
        print(f"Hata detayı: {e}")
        raise HTTPException(
            status_code=500, detail=f"YouTube ayıklama hatası: {str(e)}"
        )


@app.get("/download/{filename}")
def download_audio(filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(file_path, media_type="audio/mp4", filename=filename)


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
