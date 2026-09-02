"""参数推荐服务:知识图谱 + 遗传算法 + 预测模型 三大模块协同

协同流程(方案设计 2.3.5):
  用户输入条件(产品/材料/设备)
    → 图谱模块检索历史相似案例(生产记录库 + 数据集合格样本)
    → 优化模块(NSGA-II)在材料允许范围内生成候选参数 Pareto 集
    → 预测模块评估候选参数质量(适应度函数内完成)
    → 返回最优推荐 + 备选方案 + 历史案例 + 置信度说明
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import (EQUIPMENTS, FEATURES, MATERIALS, PROCESSED_DIR,
                        PRODUCT_TYPES)
from app.db import ProductionRecord, SessionLocal
from app.services.kg_service import kg
from app.services.model_service import ModelService
from app.services.optimizer import NSGA2Optimizer, energy
from app.services.rule_diagnosis import diagnose

# 历史案例检索参数
N_HISTORY = 5


def _material_rec_ranges(material: str) -> dict:
    """该材料各特征的推荐范围(来自领域知识)"""
    from app.config import GLOBAL_RANGES
    rec = {}
    for f in FEATURES:
        cfg = MATERIALS[material].get(f) or GLOBAL_RANGES[f]
        if "rec" in cfg:
            rec[f] = cfg["rec"]
    return rec


def history_cases(material: str, n: int = N_HISTORY) -> list[dict]:
    """检索历史相似案例: 优先查生产记录库, 为空时回退到数据集合格样本"""
    cases: list[dict] = []

    # 1) 生产记录库中该材料的合格记录(最近优先)
    with SessionLocal() as db:
        rows = db.execute(
            select(ProductionRecord)
            .where(ProductionRecord.material == material,
                   ProductionRecord.quality == 1)
            .order_by(ProductionRecord.created_at.desc())
            .limit(n)
        ).scalars().all()
        for r in rows:
            cases.append({
                "source": f"生产记录 #{r.id}",
                "equipment": r.equipment,
                "params": {f: round(float(getattr(r, f)), 2) for f in FEATURES},
                "quality": 1,
            })
        # 2) 修正反馈中合格的正确参数(老师傅经验)
        from app.db import FeedbackRecord
        fbs = db.execute(
            select(FeedbackRecord)
            .where(FeedbackRecord.material == material,
                   FeedbackRecord.quality_after == 1)
            .order_by(FeedbackRecord.created_at.desc())
            .limit(n)
        ).scalars().all()
        for f in fbs:
            params = json.loads(f.corrected_params)
            cases.append({
                "source": f"师傅修正 #{f.id}",
                "equipment": "",
                "params": {k: round(float(params[k]), 2) for k in FEATURES},
                "quality": 1,
            })

    # 3) 回退: 数据集中该材料的合格样本(按推荐范围中心距离取近邻)
    if len(cases) < n:
        df = pd.read_csv(PROCESSED_DIR / "dataset.csv", encoding="utf-8-sig")
        ok = df[(df["material"] == material) & (df["quality"] == 1)].copy()
        if not ok.empty:
            rec = _material_rec_ranges(material)
            center = {f: (np.mean(r) if r[0] is not None else None)
                      for f, r in rec.items()}
            feats = [f for f in FEATURES if center[f] is not None]
            # 按与推荐范围中心的欧氏距离取近邻作为相似案例
            ok["_dist"] = np.sum(
                [(ok[f] - center[f]) ** 2 for f in feats], axis=0)
            ok = ok.sort_values("_dist").head(n - len(cases))
            for _, row in ok.iterrows():
                cases.append({
                    "source": "历史数据集",
                    "equipment": "",
                    "params": {f: round(float(row[f]), 2) for f in FEATURES},
                    "quality": int(row["quality"]),
                })
    return cases[:n]


def _format_front(front: list[dict], material: str) -> list[dict]:
    """Pareto 前沿格式化 + 规则诊断附加信息"""
    out = []
    for s in front:
        diag = diagnose(s["params"], material, rng=np.random.default_rng(0))
        out.append({**s, "rule_check": diag["defect_type"],
                    "violations": diag["violations"]})
    return out


def recommend(product_type: str, material: str, equipment: str,
              pop_size: int = 80, n_gen: int = 30) -> dict:
    """完整推荐流程"""
    if material not in MATERIALS:
        raise ValueError(f"不支持的材料: {material},可选 {list(MATERIALS)}")

    ms = ModelService.get()
    profile = kg.material_profile(material)

    # 1) 历史相似案例(图谱/数据库)
    cases = history_cases(material)

    # 2) NSGA-II 多目标优化(Pareto 前沿)
    opt = NSGA2Optimizer(ms.quality_model, material)
    front = opt.optimize(pop_size=pop_size, n_gen=n_gen)
    front = _format_front(front, material)

    # 3) 推荐解: 质量优先、能耗兼顾
    best = opt.recommend(front)
    best_params = best["params"]
    best_diag = diagnose(best_params, material, rng=np.random.default_rng(0))
    pred = ms.predict_quality(best_params, material)

    # 置信度说明: 合格概率 + 模型指标 + 是否在推荐区间内
    rec = _material_rec_ranges(material)
    in_rec = sum(
        1 for f in FEATURES if rec[f][0] is not None
        and rec[f][0] <= best_params[f] <= rec[f][1])
    n_checked = sum(1 for f in FEATURES if rec[f][0] is not None)

    return {
        "inputs": {"product_type": product_type, "material": material,
                   "equipment": equipment},
        "recommended": {
            "params": best_params,
            "quality_prob": best["quality_prob"],
            "energy_proxy": best["energy"],
            "rule_check": best_diag["defect_type"],
            "model": ms.meta.get("quality_model", "xgboost"),
        },
        "confidence": {
            "quality_prob": best["quality_prob"],
            "model_auc": ms.meta["quality_metrics"][ms.meta["quality_model"]][
                "roc_auc"],
            "in_rec_ratio": round(in_rec / max(n_checked, 1), 3),
            "note": "合格概率由XGBoost模型评估;能耗代理=循环时间+0.3×熔体温度",
        },
        "pareto_front": front[:12],
        "history_cases": cases,
        "material_profile": {
            "label": MATERIALS[material]["label"],
            "rec_ranges": rec,
            "equipments": [e["name"] for e in profile["equipments"]],
            "rules": [r["name"] for r in profile["rules"]],
        },
    }
