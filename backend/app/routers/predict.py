"""质量预测 API"""
import sys
from pathlib import Path

import numpy as np
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.schemas import PredictRequest
from app.services.kg_service import kg
from app.services.model_service import ModelService, predict
from app.services.rule_diagnosis import diagnose

router = APIRouter(prefix="/api/predict", tags=["质量预测"])


@router.post("/quality")
def predict_quality(req: PredictRequest):
    """质量预测: 给定工艺参数组合 -> 合格概率 + 缺陷类型 + 图谱根因与对策"""
    params = req.params.dict_params()
    result = predict(params, req.material)
    # 知识图谱规则诊断(双重诊断: ML 模型 + 领域规则)
    diag = diagnose(params, req.material, rng=np.random.default_rng(0))
    # 缺陷根因与对策(图谱检索)
    defect_name = result["defect_type"] if result["quality"] == 0 else diag["defect_type"]
    analysis = kg.defect_analysis(defect_name) if defect_name != "合格" else None
    return {
        "material": req.material,
        "params": params,
        "quality": result["quality"],
        "quality_prob": result["quality_prob"],
        "defect_type": result["defect_type"],
        "defect_distribution": result["distribution"],
        "rule_diagnosis": diag,
        "defect_analysis": analysis,
    }


@router.post("/defect")
def predict_defect(req: PredictRequest):
    """缺陷类型预测: 返回 8 类缺陷概率分布"""
    ms = ModelService.get()
    return ms.predict_defect(req.params.dict_params(), req.material)


@router.get("/model/info")
def model_info():
    """模型信息与评估指标"""
    ms = ModelService.get()
    return ms.metrics
