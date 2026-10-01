import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="AudioSetter YouTube Engine")

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


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
      "format": "bestaudio[ext=m4a]/bestaudio/best",
      "outtmpl": output_template,
      "quiet": True,
      "no_warnings": True,
      "nocheckcertificate": True,
  }

  try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(url, download=True)
      title = info.get("title", "AudioSetter Track")
      ext = info.get("ext", "m4a")
      final_filename = f"{file_id}.{ext}"

      # Dosya kontrolü
      file_path = os.path.join(DOWNLOAD_DIR, final_filename)
      if not os.path.exists(file_path):
        for f in os.listdir(DOWNLOAD_DIR):
          if f.startswith(file_id):
            final_filename = f
            break

      return {
          "status": "success",
          "title": title,
          "download_url": f"/download/{final_filename}",
      }
  except Exception as e:
    raise HTTPException(
        status_code=500, detail=f"YouTube ayıklama hatası: {str(e)}"
    )


@app.get("/download/{filename}")
def download_audio(filename: str):
  file_path = os.path.join(DOWNLOAD_DIR, filename)
  if not os.path.exists(file_path):
    raise HTTPException(status_code=404, detail="Dosya bulunamadı")
  return FileResponse(file_path, media_type="audio/mp4", filename=filename)


@app.get("/health")
def health_check():
  return {"status": "ok"}


if __name__ == "__main__":
  import uvicorn

  port = int(os.environ.get("PORT", 8000))
  uvicorn.run(app, host="0.0.0.0", port=port)
