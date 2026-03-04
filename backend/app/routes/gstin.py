from fastapi import APIRouter
from app.services.gstin_validator import validate_gstin

router = APIRouter(prefix="/gstin", tags=["GSTIN"])

@router.get("/validate/{gstin}")
def validate(gstin: str):
    result = validate_gstin(gstin)
    return result