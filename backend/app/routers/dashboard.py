"""数据看板 API:生产统计、质量趋势、模型指标聚合"""
import json
import sys
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import DEFECT_TYPES, MATERIALS
from app.db import ModelVersion, SessionLocal
from app.routers.records import record_stats
from app.services.model_service import ModelService

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


@router.get("")
def dashboard():
    """看板聚合数据"""
    with SessionLocal() as db:
        stats = record_stats(db)
        versions = db.execute(select(ModelVersion)
                              .order_by(ModelVersion.trained_at)).scalars().all()

    ms = ModelService.get()
    quality_metrics = ms.metrics["quality_metrics"][ms.metrics["quality_model"]]
    model_trend = [{
        "version": v.id,
        "trained_at": v.trained_at.strftime("%m-%d %H:%M"),
        "accuracy": json.loads(v.metrics).get("accuracy", 0) if v.metrics else 0,
        "samples": v.samples,
    } for v in versions]

    return {
        "record_stats": stats,
        "model": {
            "name": ms.metrics["quality_model"],
            "metrics": quality_metrics,
            "trained_samples": ms.metrics["trained_samples"],
            "defect_accuracy": ms.metrics["defect_metrics"]["accuracy"],
            "defect_macro_f1": ms.metrics["defect_metrics"]["macro_f1"],
            "feature_importance": ms.metrics["feature_importance"][:10],
            "model_trend": model_trend,
        },
        "defect_types": DEFECT_TYPES,
        "materials": {k: v["label"] for k, v in MATERIALS.items()},
    }
