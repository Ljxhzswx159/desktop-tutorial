"""模型训练脚本:阶段2-模型训练

1. 质量预测(二分类): XGBoost 与随机森林对比, 5 折交叉验证, 择优保存;
2. 缺陷类型预测(多分类): XGBoost, 基于合成数据(带缺陷标注)训练;
3. 保存模型、评估指标与特征重要性。

运行: py -3.13 backend/scripts/train.py
"""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, classification_report, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
from app.config import DEFECT_TYPES, FEATURES, MODEL_DIR, PROCESSED_DIR

RNG = 42


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(PROCESSED_DIR / "dataset.csv", encoding="utf-8-sig")
    # 材料 one-hot 编码
    mat_dummy = pd.get_dummies(df["material"], prefix="mat").astype(int)
    X = pd.concat([df[FEATURES], mat_dummy], axis=1)
    y_quality = df["quality"].values
    # 缺陷多分类仅用合成数据(真实数据的缺陷类型为"未知")
    synth = df[df["source"] == "synthetic"].copy()
    X_s = pd.concat([synth[FEATURES],
                     pd.get_dummies(synth["material"], prefix="mat").astype(int)],
                    axis=1)
    le = LabelEncoder()
    y_defect = le.fit_transform(synth["defect_type"].values)
    return X, y_quality, X_s, y_defect, le


def eval_binary(model, X_test, y_test) -> dict:
    proba = model.predict_proba(X_test)[:, 1]
    pred = model.predict(X_test)
    return {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "precision": round(float(precision_score(y_test, pred)), 4),
        "recall": round(float(recall_score(y_test, pred)), 4),
        "f1": round(float(f1_score(y_test, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, proba)), 4),
    }


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    X, y_quality, X_s, y_defect, le = load_data()
    print(f"质量二分类: {X.shape[0]} 样本 × {X.shape[1]} 特征")
    print(f"缺陷多分类: {X_s.shape[0]} 样本 × {X_s.shape[1]} 特征, "
          f"类别 {le.classes_.tolist()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_quality, test_size=0.2, stratify=y_quality, random_state=RNG)

    # ---------- 1. 质量预测模型对比 ----------
    results = {}
    for name, model in [
        ("xgboost", XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.08,
                                  subsample=0.9, colsample_bytree=0.9,
                                  eval_metric="logloss", random_state=RNG)),
        ("random_forest", RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=2,
            n_jobs=-1, random_state=RNG)),
    ]:
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RNG)
        cv_scores = cross_val_score(model, X, y_quality, cv=cv,
                                    scoring="roc_auc", n_jobs=-1)
        model.fit(X_train, y_train)
        m = eval_binary(model, X_test, y_test)
        m["cv_auc_mean"] = round(float(cv_scores.mean()), 4)
        m["cv_auc_std"] = round(float(cv_scores.std()), 4)
        results[name] = m
        print(f"\n[{name}] 5折CV AUC: {m['cv_auc_mean']}±{m['cv_auc_std']}")
        print(f"  测试集: acc={m['accuracy']} f1={m['f1']} auc={m['roc_auc']}")

    # 择优保存质量模型
    best_name = max(results, key=lambda k: results[k]["roc_auc"])
    print(f"\n选用质量预测模型: {best_name}")
    if best_name == "xgboost":
        quality_model = XGBClassifier(n_estimators=300, max_depth=6,
                                      learning_rate=0.08, subsample=0.9,
                                      colsample_bytree=0.9,
                                      eval_metric="logloss", random_state=RNG)
    else:
        quality_model = RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=2,
            n_jobs=-1, random_state=RNG)
    quality_model.fit(X, y_quality)
    joblib.dump(quality_model, MODEL_DIR / "quality_model.joblib")

    # ---------- 2. 缺陷类型多分类模型 ----------
    Xs_train, Xs_test, ys_train, ys_test = train_test_split(
        X_s, y_defect, test_size=0.2, stratify=y_defect, random_state=RNG)
    defect_model = XGBClassifier(n_estimators=400, max_depth=7,
                                 learning_rate=0.08, eval_metric="mlogloss",
                                 random_state=RNG)
    defect_model.fit(Xs_train, ys_train)
    ys_pred = defect_model.predict(Xs_test)
    defect_metrics = {
        "accuracy": round(float(accuracy_score(ys_test, ys_pred)), 4),
        "macro_f1": round(float(f1_score(ys_test, ys_pred, average="macro")), 4),
        "report": classification_report(ys_test, ys_pred,
                                        target_names=le.classes_.tolist()),
    }
    print("\n[缺陷多分类] "
          f"acc={defect_metrics['accuracy']} macro_f1={defect_metrics['macro_f1']}")
    print(defect_metrics["report"])
    joblib.dump(defect_model, MODEL_DIR / "defect_model.joblib")
    joblib.dump(le, MODEL_DIR / "defect_label_encoder.joblib")

    # ---------- 3. 特征与元信息 ----------
    importance = quality_model.feature_importances_
    feat_imp = sorted(zip(X.columns, importance), key=lambda t: -t[1])
    meta = {
        "quality_model": best_name,
        "quality_metrics": results,
        "defect_metrics": {k: v for k, v in defect_metrics.items() if k != "report"},
        "feature_columns": list(X.columns),
        "defect_classes": le.classes_.tolist(),
        "feature_importance": [[f, round(float(i), 4)] for f, i in feat_imp],
        "trained_samples": int(len(X)),
        "defect_trained_samples": int(len(X_s)),
    }
    (MODEL_DIR / "model_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n特征重要性 Top10:")
    for f, i in feat_imp[:10]:
        print(f"  {f}: {i:.4f}")
    print(f"\n模型已保存至 {MODEL_DIR}")


if __name__ == "__main__":
    main()
