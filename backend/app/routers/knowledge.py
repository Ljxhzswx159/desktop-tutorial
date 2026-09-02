"""知识检索 API"""
import sys
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import MATERIALS
from app.schemas import DiagnoseRequest, SearchRequest
from app.services.kg_service import kg
from app.services.rule_diagnosis import diagnose

router = APIRouter(prefix="/api/knowledge", tags=["知识检索"])


@router.post("/search")
def search(req: SearchRequest):
    """知识检索: 支持自然语言/结构化关键词查询, 返回知识条目与关联子图"""
    return kg.search(req.query, limit=req.limit)


@router.post("/diagnose")
def diagnose_params(req: DiagnoseRequest):
    """规则诊断: 参数组合 -> 违规明细 + 缺陷类型 + 图谱对策"""
    diag = diagnose(req.params.dict_params(), req.material,
                    rng=np.random.default_rng(0))
    analysis = kg.defect_analysis(diag["defect_type"]) \
        if diag["defect_type"] != "合格" else None
    return {"material": req.material, "diagnosis": diag, "analysis": analysis}


@router.get("/material/{material}")
def material_profile(material: str):
    """材料工艺画像: 材料特性 + 适用设备 + 相关工艺规则"""
    if material not in MATERIALS:
        raise HTTPException(404, f"未知材料 {material}, 可选 {list(MATERIALS)}")
    return kg.material_profile(material)


@router.get("/materials")
def materials():
    """可选材料清单(含推荐参数范围)"""
    return {"materials": MATERIALS}


@router.get("/graph")
def graph():
    """知识图谱全图(前端可视化)"""
    return kg.full_graph()
