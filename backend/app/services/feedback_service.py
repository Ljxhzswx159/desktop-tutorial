"""反馈修正服务:老师傅手动调整参数 -> 反哺模型在线学习

流程:
  1. 操作员提交修正反馈(原始参数 + 师傅修正参数 + 修正后质量)
  2. 积累的未应用反馈可触发模型再训练:
     - 修正后合格 -> 修正参数作为正样本加入训练集
     - 修正后不合格 -> 原始/修正参数作为负样本加入训练集
  3. 重训 XGBoost 质量模型,记录模型版本,标记反馈为已应用
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sqlalchemy import select
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import FEATURES, MATERIALS, MODEL_DIR, PROCESSED_DIR
from app.db import FeedbackRecord, ModelVersion, SessionLocal


def _load_training_data() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(PROCESSED_DIR / "dataset.csv", encoding="utf-8-sig")
    mat_dummy = pd.get_dummies(df["material"], prefix="mat").astype(int)
    X = pd.concat([df[FEATURES], mat_dummy], axis=1)
    return X, df["quality"]


def _feedback_rows() -> list[dict]:
    with SessionLocal() as db:
        fbs = db.execute(
            select(FeedbackRecord).where(FeedbackRecord.applied.is_(False))
        ).scalars().all()
        return [
            {"material": f.material,
             "corrected": json.loads(f.corrected_params),
             "original": json.loads(f.original_params),
             "quality_after": f.quality_after}
            for f in fbs
        ]


def retrain() -> dict:
    """应用未学习的反馈,增量重训质量预测模型"""
    fb_rows = _feedback_rows()
    if not fb_rows:
        return {"retrained": False, "message": "没有待应用的反馈数据"}

    X, y = _load_training_data()
    material_cols = [c for c in X.columns if c.startswith("mat_")]
    extra_rows = []
    for fb in fb_rows:
        for params, label in [
            (fb["corrected"], fb["quality_after"]),          # 修正参数+实际结果
            (fb["original"], 0 if fb["quality_after"] == 1 else 0),
        ]:
            row = {**{f: params[f] for f in FEATURES},
                   **{c: 0 for c in material_cols}}
            row[f"mat_{fb['material']}"] = 1
            extra_rows.append((row, label))
    X_new = pd.concat([X, pd.DataFrame([r for r, _ in extra_rows])],
                      ignore_index=True)
    y_new = pd.concat([y, pd.Series([l for _, l in extra_rows])],
                      ignore_index=True)

    model = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.08,
                          subsample=0.9, colsample_bytree=0.9,
                          eval_metric="logloss", random_state=42)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_new, y_new, test_size=0.2, stratify=y_new, random_state=42)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    pred = model.predict(X_te)
    metrics = {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "f1": round(float(f1_score(y_te, pred)), 4),
        "auc": round(float(roc_auc_score(y_te, proba)), 4),
    }
    model.fit(X_new, y_new)
    joblib.dump(model, MODEL_DIR / "quality_model.joblib")

    # 更新元信息
    meta_path = MODEL_DIR / "model_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["quality_metrics"][meta["quality_model"]].update({
        "accuracy": metrics["accuracy"], "f1": metrics["f1"],
        "roc_auc": metrics["auc"]})
    meta["trained_samples"] = int(len(X_new))
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    # 记录版本,标记反馈已应用
    with SessionLocal() as db:
        db.add(ModelVersion(samples=int(len(X_new)),
                            feedback_used=len(fb_rows),
                            metrics=json.dumps(metrics),
                            note="反馈在线学习"))
        for f in db.execute(select(FeedbackRecord).where(
                FeedbackRecord.applied.is_(False))).scalars().all():
            f.applied = True
        db.commit()

    from app.services.model_service import ModelService
    ModelService.reload()
    return {"retrained": True, "feedback_used": len(fb_rows),
            "samples": int(len(X_new)), "metrics": metrics}
