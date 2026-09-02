"""模型服务:质量预测与缺陷分类模型的加载与推理封装"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import FEATURES, MODEL_DIR


class ModelService:
    """单例模型服务(启动时加载,避免每次请求重新反序列化)"""

    _instance: "ModelService | None" = None

    def __init__(self) -> None:
        self.quality_model = joblib.load(MODEL_DIR / "quality_model.joblib")
        self.defect_model = joblib.load(MODEL_DIR / "defect_model.joblib")
        self.defect_le = joblib.load(MODEL_DIR / "defect_label_encoder.joblib")
        self.meta = json.loads(
            (MODEL_DIR / "model_meta.json").read_text(encoding="utf-8"))
        self.material_cols = [c for c in
                              self.quality_model.feature_names_in_
                              if c.startswith("mat_")]

    @classmethod
    def get(cls) -> "ModelService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reload(cls) -> "ModelService":
        """模型重训(反馈学习)后重新加载"""
        cls._instance = None
        return cls.get()

    def _row(self, params: dict, material: str) -> pd.DataFrame:
        row = {**{f: params[f] for f in FEATURES},
               **{c: 0 for c in self.material_cols}}
        row[f"mat_{material}"] = 1
        return pd.DataFrame([row])[self.quality_model.feature_names_in_]

    def predict_quality(self, params: dict, material: str) -> dict:
        """质量预测: 返回合格概率与预测标签"""
        row = self._row(params, material)
        proba = float(self.quality_model.predict_proba(row)[0, 1])
        return {"quality_prob": round(proba, 4),
                "quality": 1 if proba >= 0.5 else 0}

    def predict_defect(self, params: dict, material: str) -> dict:
        """缺陷类型预测: 返回各缺陷类别概率分布"""
        row = self._row(params, material)
        proba = self.defect_model.predict_proba(row)[0]
        order = sorted(range(len(proba)), key=lambda i: -proba[i])
        dist = [{"defect": self.defect_le.classes_[i],
                 "prob": round(float(proba[i]), 4)} for i in order]
        return {"defect_type": dist[0]["defect"],
                "distribution": dist}

    @property
    def metrics(self) -> dict:
        return self.meta


def predict(params: dict, material: str) -> dict:
    """组合预测: 质量 + 缺陷类型(供 API 与优化评估共用)"""
    ms = ModelService.get()
    return {**ms.predict_quality(params, material),
            **ms.predict_defect(params, material)}
