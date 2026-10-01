import os
import uuid
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="AudioSetter YouTube Engine")

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Güvenilir açık kaynak Cobalt API uç noktası
COBALT_API_URL = "https://api.cobalt.tools"


class FetchRequest(BaseModel):
    url: str


@app.post("/extract-audio")
async def extract_audio(req: FetchRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Geçersiz URL")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "AudioSetter/1.0",
    }

    payload = {
        "url": url,
        "downloadMode": "audio",
        "audioFormat": "mp3",
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            # 1. Cobalt API'ye isteği gönder
            response = await client.post(COBALT_API_URL, json=payload, headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=500,
                    detail=f"Ses motoru yanıt vermedi: {response.text}",
                )

            data = response.json()
            stream_url = data.get("url")
            filename_header = data.get("filename", "AudioSetter_Track.mp3")

            if not stream_url:
                raise HTTPException(
                    status_code=500,
                    detail="Ses akış adresi alınamadı.",
                )

            # 2. Sesi sunucunun geçici dizinine indir
            file_id = str(uuid.uuid4())[:8]
            final_filename = f"{file_id}.mp3"
            file_path = os.path.join(DOWNLOAD_DIR, final_filename)

            audio_res = await client.get(stream_url)
            if audio_res.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(audio_res.content)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="Ses dosyası indirilemedi.",
                )

            track_title = filename_header.replace(".mp3", "")

            return {
                "status": "success",
                "title": track_title,
                "download_url": f"/download/{final_filename}",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"İndirme motoru hatası: {str(e)}"
        )


@app.get("/download/{filename}")
def download_audio(filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(file_path, media_type="audio/mpeg", filename=filename)


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
