from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict
import yt_dlp
import asyncio
import os
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="YouTube Downloader API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Replace with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create cache directory if it doesn't exist
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

# Rate limiting configuration
RATE_LIMIT = {
    "window_seconds": 3600,  # 1 hour
    "max_requests": 100      # max requests per hour
}

rate_limit_store: Dict[str, List[float]] = {}

class VideoURL(BaseModel):
    url: HttpUrl

    @property
    def video_id(self) -> str:
        parsed = urlparse(str(self.url))
        if 'youtu.be' in parsed.netloc:
            return parsed.path[1:]
        if 'youtube.com' in parsed.netloc:
            query = dict(q.split('=') for q in parsed.query.split('&') if '=' in q)
            return query.get('v', '')
        raise ValueError("Invalid YouTube URL")

class VideoFormat(BaseModel):
    format_id: str
    ext: str
    quality: str
    filesize: Optional[int]
    resolution: Optional[str]
    fps: Optional[int]
    vcodec: Optional[str]
    acodec: Optional[str]

class VideoInfo(BaseModel):
    title: str
    thumbnail: str
    duration: int
    formats: List[VideoFormat]
    description: Optional[str]
    view_count: Optional[int]
    upload_date: Optional[str]

def check_rate_limit(ip: str) -> bool:
    current_time = time.time()
    if ip not in rate_limit_store:
        rate_limit_store[ip] = []
    
    # Remove old requests
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] 
                           if current_time - t < RATE_LIMIT["window_seconds"]]
    
    if len(rate_limit_store[ip]) >= RATE_LIMIT["max_requests"]:
        return False
    
    rate_limit_store[ip].append(current_time)
    return True

def get_cache_key(video_id: str) -> Path:
    return CACHE_DIR / f"{video_id}.json"

def get_cached_info(video_id: str) -> Optional[dict]:
    cache_file = get_cache_key(video_id)
    if cache_file.exists():
        cache_data = json.loads(cache_file.read_text())
        cache_time = datetime.fromisoformat(cache_data['cache_time'])
        if datetime.utcnow() - cache_time < timedelta(hours=1):
            return cache_data['info']
    return None

def save_cache_info(video_id: str, info: dict):
    cache_data = {
        'cache_time': datetime.utcnow().isoformat(),
        'info': info
    }
    cache_file = get_cache_key(video_id)
    cache_file.write_text(json.dumps(cache_data))

class YTDLPLogger:
    def debug(self, msg):
        if msg.startswith('[debug] '):
            logger.debug(msg)
    def info(self, msg):
        logger.info(msg)
    def warning(self, msg):
        logger.warning(msg)
    def error(self, msg):
        logger.error(msg)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    if not check_rate_limit(request.client.host):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."}
        )
    response = await call_next(request)
    return response

@app.post("/api/video-info")
async def get_video_info(video: VideoURL):
    try:
        # Check cache first
        cached_info = get_cached_info(video.video_id)
        if cached_info:
            return cached_info

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'logger': YTDLPLogger(),
            # Cookie handling
            'cookiesfrombrowser': ('chrome',),  # Will try to import cookies from Chrome
            # Format handling
            'format': 'best',
            # Geo-restriction bypass
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            # Network settings
            'socket_timeout': 10,
            'retries': 3,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(video.url), download=False)
            
            formats = [
                VideoFormat(
                    format_id=f['format_id'],
                    ext=f.get('ext', ''),
                    quality=f.get('format_note', ''),
                    filesize=f.get('filesize'),
                    resolution=f.get('resolution'),
                    fps=f.get('fps'),
                    vcodec=f.get('vcodec'),
                    acodec=f.get('acodec')
                )
                for f in info.get('formats', [])
                if f.get('ext') in ['mp4', 'webm', 'm4a', 'mp3']
            ]
            
            video_info = VideoInfo(
                title=info['title'],
                thumbnail=info['thumbnail'],
                duration=info['duration'],
                formats=formats,
                description=info.get('description'),
                view_count=info.get('view_count'),
                upload_date=info.get('upload_date')
            )
            
            # Cache the results
            save_cache_info(video.video_id, video_info.dict())
            
            return video_info

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Video download error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/api/download")
async def download_video(video: VideoURL, format_id: str):
    try:
        output_dir = Path("downloads")
        output_dir.mkdir(exist_ok=True)

        ydl_opts = {
            'format': format_id,
            'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'logger': YTDLPLogger(),
            # Cookie handling
            'cookiesfrombrowser': ('chrome',),
            # Format handling
            'format_sort': ['res:1080p', 'ext:mp4:m4a'],
            # Geo-restriction bypass
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            # Network settings
            'socket_timeout': 10,
            'retries': 3,
            # Fragment handling
            'fragment_retries': 10,
            'skip_unavailable_fragments': False,
            # Extra features
            'keepvideo': True,
            'overwrites': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(str(video.url), download=True)
            filename = ydl.prepare_filename(info)
            
            if not os.path.exists(filename):
                raise HTTPException(status_code=404, detail="File not found after download")
            
            def iterfile():
                with open(filename, 'rb') as f:
                    while chunk := f.read(8192):
                        yield chunk
                # Clean up after streaming
                os.unlink(filename)
            
            return StreamingResponse(
                iterfile(),
                media_type='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{os.path.basename(filename)}"'
                }
            )

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Video download error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
