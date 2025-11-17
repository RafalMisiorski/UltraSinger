"""API routes for UltraSinger web application"""

import logging
import zipfile
import io
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse

from api.models import (
    CreateJobRequest,
    JobResponse,
    JobListResponse,
    UploadResponse,
    JobStatus,
    JobProgress,
)
from services.queue_service import job_queue
from services.youtube_service import get_video_info
from utils.config import settings
from utils.validators import is_valid_youtube_url, is_valid_audio_file, sanitize_filename

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


@router.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """Upload an audio file for processing"""
    # Validate file type
    if not is_valid_audio_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Supported formats: MP3, WAV, OGG, M4A, FLAC"
        )

    # Sanitize filename
    safe_filename = sanitize_filename(file.filename)

    # Check file size
    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / 1024 / 1024}MB"
        )

    # Save file
    file_path = settings.upload_dir / safe_filename
    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Uploaded file: {safe_filename} ({len(content)} bytes)")

    return UploadResponse(
        filename=safe_filename,
        size=len(content),
        upload_id=safe_filename,
    )


@router.get("/youtube/preview")
async def preview_youtube(url: str):
    """Get YouTube video metadata without downloading"""
    if not is_valid_youtube_url(url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        info = await get_video_info(url)
        return info
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch YouTube video information: {str(e)}"
        )


@router.post("/jobs/create", response_model=JobResponse)
async def create_job(request: CreateJobRequest):
    """Create a new processing job"""
    # Validate YouTube URL if source is YouTube
    if request.source.value == "youtube":
        if not request.youtube_url or not is_valid_youtube_url(request.youtube_url):
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    # Validate upload file if source is upload
    if request.source.value == "upload":
        if not request.upload_filename:
            raise HTTPException(status_code=400, detail="upload_filename is required for upload source")
        upload_path = settings.upload_dir / request.upload_filename
        if not upload_path.exists():
            raise HTTPException(status_code=404, detail="Uploaded file not found")

    # Create job
    job_id = job_queue.create_job(
        source=request.source,
        language=request.language,
        quality=request.quality,
        youtube_url=request.youtube_url,
        upload_filename=request.upload_filename,
        custom_name=request.custom_name,
        is_duet=request.is_duet,
        speaker_1_name=request.speaker_1_name,
        speaker_2_name=request.speaker_2_name,
    )

    job = job_queue.get_job(job_id)
    return _job_to_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job status and details"""
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _job_to_response(job)


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 50, offset: int = 0):
    """List all jobs"""
    jobs = job_queue.list_jobs()
    total = len(jobs)

    # Apply pagination
    jobs = jobs[offset:offset + limit]

    return JobListResponse(
        jobs=[_job_to_response(job) for job in jobs],
        total=total,
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Cancel and delete a job"""
    success = job_queue.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"message": "Job deleted successfully"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a processing job"""
    success = job_queue.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or already finished")

    return {"message": "Job cancelled successfully"}


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry a failed or cancelled job"""
    new_job_id = job_queue.retry_job(job_id)
    if not new_job_id:
        raise HTTPException(
            status_code=400,
            detail="Job not found or cannot be retried (must be in failed or cancelled status)"
        )

    new_job = job_queue.get_job(new_job_id)
    return _job_to_response(new_job)


@router.get("/jobs/{job_id}/download")
async def download_result(job_id: str, file_type: str = "main"):
    """
    Download the generated UltraStar file(s)

    Args:
        job_id: Job ID
        file_type: Type of file to download
            - "main": Primary result file (duet for duet jobs, solo otherwise)
            - "duet": Duet file with P1/P2 markers (duet jobs only)
            - "solo1": First speaker's solo file (duet jobs only)
            - "solo2": Second speaker's solo file (duet jobs only)
    """
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")

    # Select which file to download based on file_type
    file_path = None

    if file_type == "duet" and job.is_duet:
        file_path = job.duet_result_file
    elif file_type == "solo1" and job.is_duet:
        file_path = job.solo_1_result_file
    elif file_type == "solo2" and job.is_duet:
        file_path = job.solo_2_result_file
    elif file_type == "main":
        file_path = job.result_file
    else:
        # Invalid file_type for this job
        if not job.is_duet:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file_type}' is only available for duet jobs"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file_type: {file_type}. Must be one of: main, duet, solo1, solo2"
            )

    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Result file not found for type: {file_type}")

    return FileResponse(
        file_path,
        media_type="text/plain",
        filename=file_path.name,
    )


@router.get("/jobs/{job_id}/download-zip")
async def download_all_as_zip(job_id: str):
    """Download all duet files as a ZIP archive"""
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")

    if not job.is_duet:
        raise HTTPException(status_code=400, detail="ZIP download is only available for duet jobs")

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add duet file
            if job.duet_result_file and job.duet_result_file.exists():
                zip_file.write(job.duet_result_file, job.duet_result_file.name)

            # Add solo files
            if job.solo_1_result_file and job.solo_1_result_file.exists():
                zip_file.write(job.solo_1_result_file, job.solo_1_result_file.name)

            if job.solo_2_result_file and job.solo_2_result_file.exists():
                zip_file.write(job.solo_2_result_file, job.solo_2_result_file.name)

        # Prepare ZIP for download
        zip_buffer.seek(0)

        filename = f"{job.title or 'duet'}_all_files.zip".replace(" ", "_")

        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Failed to create ZIP for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create ZIP archive")


@router.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates"""
    await websocket.accept()

    # Check if job exists
    job = job_queue.get_job(job_id)
    if not job:
        await websocket.close(code=4004, reason="Job not found")
        return

    # Register websocket
    await job_queue.register_websocket(job_id, websocket)

    try:
        # Send initial status
        await websocket.send_json({
            "job_id": job_id,
            "status": job.status.value,
            "step": job.current_step.value if job.current_step else None,
            "percentage": job.progress_percentage,
            "message": job.progress_message,
            "elapsed_seconds": job.elapsed_seconds,
        })

        # Keep connection alive and listen for client messages
        while True:
            # Wait for any message (ping/pong, etc.)
            await websocket.receive_text()

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        # Unregister websocket
        await job_queue.unregister_websocket(job_id, websocket)


def _job_to_response(job) -> JobResponse:
    """Convert Job to JobResponse"""
    progress = None
    if job.current_step:
        progress = JobProgress(
            step=job.current_step,
            percentage=job.progress_percentage,
            message=job.progress_message,
            elapsed_seconds=job.elapsed_seconds,
        )

    # Get queue position
    queue_position = job_queue.get_queue_position(job.job_id)

    return JobResponse(
        job_id=job.job_id,
        source=job.source,
        status=job.status,
        language=job.language,
        quality=job.quality,
        title=job.title,
        custom_name=job.custom_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
        progress=progress,
        error_message=job.error_message,
        result_file_path=str(job.result_file) if job.result_file else None,
        estimated_duration_seconds=job.estimated_duration_seconds,
        elapsed_seconds=job.elapsed_seconds,
        youtube_thumbnail=job.youtube_thumbnail,
        youtube_duration=job.youtube_duration,
        youtube_channel=job.youtube_channel,
        queue_position=queue_position,
        is_duet=job.is_duet,
        speaker_1_name=job.speaker_1_name,
        speaker_2_name=job.speaker_2_name,
        duet_result_file_path=str(job.duet_result_file) if job.duet_result_file else None,
        solo_1_result_file_path=str(job.solo_1_result_file) if job.solo_1_result_file else None,
        solo_2_result_file_path=str(job.solo_2_result_file) if job.solo_2_result_file else None,
    )
