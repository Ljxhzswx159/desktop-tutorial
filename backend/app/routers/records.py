"""数据记录 API:生产数据录入与历史查询"""
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import FEATURES
from app.db import ProductionRecord, get_session
from app.schemas import RecordCreate

router = APIRouter(prefix="/api/records", tags=["数据记录"])


def _to_dict(r: ProductionRecord) -> dict:
    return {
        "id": r.id,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        "product_type": r.product_type,
        "material": r.material,
        "equipment": r.equipment,
        "operator": r.operator,
        "params": {f: round(float(getattr(r, f)), 2) for f in FEATURES},
        "quality": r.quality,
        "defect_type": r.defect_type,
        "source": r.source,
        "note": r.note,
    }


@router.post("")
def create_record(req: RecordCreate, db: Session = Depends(get_session)):
    """录入生产记录(操作员录入实际工艺参数与检测结果)"""
    rec = ProductionRecord(**req.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return _to_dict(rec)


@router.get("")
def list_records(
    material: str = Query("", description="按材料过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    """历史记录分页查询"""
    q = select(ProductionRecord).order_by(ProductionRecord.created_at.desc())
    if material:
        q = q.where(ProductionRecord.material == material)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar()
    rows = db.execute(q.offset((page - 1) * page_size)
                      .limit(page_size)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_to_dict(r) for r in rows]}


@router.get("/stats")
def record_stats(db: Session = Depends(get_session)):
    """记录统计: 总量、合格率、按材料/缺陷分布(供看板使用)"""
    total = db.execute(select(func.count(ProductionRecord.id))).scalar()
    ok = db.execute(select(func.count(ProductionRecord.id))
                    .where(ProductionRecord.quality == 1)).scalar()
    by_material = dict(db.execute(
        select(ProductionRecord.material, func.count())
        .group_by(ProductionRecord.material)).all())
    by_defect = dict(db.execute(
        select(ProductionRecord.defect_type, func.count())
        .where(ProductionRecord.defect_type != "")
        .group_by(ProductionRecord.defect_type)).all())
    by_day = dict(db.execute(
        select(func.strftime("%Y-%m-%d", ProductionRecord.created_at),
               func.count())
        .group_by(func.strftime("%Y-%m-%d", ProductionRecord.created_at))
        .order_by(func.strftime("%Y-%m-%d", ProductionRecord.created_at))
        .limit(30)).all())
    by_day_ok = dict(db.execute(
        select(func.strftime("%Y-%m-%d", ProductionRecord.created_at),
               func.count())
        .where(ProductionRecord.quality == 1)
        .group_by(func.strftime("%Y-%m-%d", ProductionRecord.created_at))
        .limit(30)).all())
    by_material_ok = dict(db.execute(
        select(ProductionRecord.material, func.count())
        .where(ProductionRecord.quality == 1)
        .group_by(ProductionRecord.material)).all())
    return {"total": total, "ok": ok,
            "ok_rate": round(ok / total, 4) if total else 0,
            "by_material": by_material, "by_defect": by_defect,
            "by_day": by_day, "by_day_ok": by_day_ok,
            "by_material_ok": by_material_ok}
