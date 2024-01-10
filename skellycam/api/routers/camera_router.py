from fastapi import APIRouter

router = APIRouter()

DUMMY_CAMERAS = {"0": "its camera 0!", "1": "its camera 1!"}

@router.get("/camera/")
async def get_cameras():
    return DUMMY_CAMERAS

@router.get("/camera/{camera_id}")
async def get_camera_by_id(camera_id: str):
    return DUMMY_CAMERAS[camera_id] if camera_id in DUMMY_CAMERAS else ResourceWarning(f"Camera {camera_id} not found!")