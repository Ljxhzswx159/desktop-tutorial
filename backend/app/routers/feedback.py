"""反馈修正 API:人工修正参数与模型在线学习"""
import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.db import FeedbackRecord, ModelVersion, get_session
from app.schemas import FeedbackCreate
from app.services.feedback_service import retrain

router = APIRouter(prefix="/api/feedback", tags=["反馈修正"])


@router.post("")
def create_feedback(req: FeedbackCreate, db: Session = Depends(get_session)):
    """提交人工修正反馈(老师傅手动调整记录)"""
    fb = FeedbackRecord(
        material=req.material,
        operator=req.operator,
        original_params=json.dumps(req.original_params, ensure_ascii=False),
        corrected_params=json.dumps(req.corrected_params, ensure_ascii=False),
        quality_after=req.quality_after,
        defect_after=req.defect_after,
        reason=req.reason,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"id": fb.id, "created_at": fb.created_at.strftime("%Y-%m-%d %H:%M"),
            "applied": fb.applied}


@router.get("")
def list_feedback(db: Session = Depends(get_session)):
    """反馈列表(含是否已用于模型学习)"""
    rows = db.execute(select(FeedbackRecord)
                      .order_by(FeedbackRecord.created_at.desc())).scalars().all()
    return [{
        "id": f.id,
        "created_at": f.created_at.strftime("%Y-%m-%d %H:%M"),
        "material": f.material,
        "operator": f.operator,
        "original_params": json.loads(f.original_params),
        "corrected_params": json.loads(f.corrected_params),
        "quality_after": f.quality_after,
        "defect_after": f.defect_after,
        "reason": f.reason,
        "applied": f.applied,
    } for f in rows]


@router.post("/retrain")
def trigger_retrain():
    """应用未学习反馈,在线重训质量预测模型"""
    return retrain()


@router.get("/models")
def model_versions(db: Session = Depends(get_session)):
    """模型版本历史"""
    rows = db.execute(select(ModelVersion)
                      .order_by(ModelVersion.trained_at.desc())).scalars().all()
    return [{
        "id": v.id,
        "trained_at": v.trained_at.strftime("%Y-%m-%d %H:%M"),
        "samples": v.samples,
        "feedback_used": v.feedback_used,
        "metrics": json.loads(v.metrics),
        "note": v.note,
    } for v in rows]
