"""数据预处理脚本:阶段1-数据准备

流程:
1. 解析真实注塑工艺数据集(UCI 公开数据集, 1451 条, 分号分隔单列存储),
   质量标签 {1,2}->不合格(0), {3,4}->合格(1), 材料按 ABS 归类;
2. 基于领域知识(材料推荐参数范围)生成 7 种材料的合成扩展数据,
   并按工艺规则为不合格样本标注缺陷类型(翘曲/缩痕/飞边/银纹/熔接线/缺料/烧焦);
3. 合并为统一数据集 data/processed/dataset.csv, 输出元信息 dataset_meta.json;
4. 由知识图谱数据生成 Neo4j 导入脚本 data/processed/knowledge_graph.cypher。

运行: py -3.13 backend/scripts/preprocess.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
from app.config import (DEFECT_TYPES, FEATURES, GLOBAL_RANGES, MATERIALS,
                        PROCESSED_DIR, RAW_DIR, REAL_DATA_MATERIAL, KG_FILE)
from app.services.rule_diagnosis import diagnose as diagnose_params

RNG = np.random.default_rng(42)
N_SYN_PER_MATERIAL = 1000


def parse_real_data() -> pd.DataFrame:
    """解析真实数据集: 分号分隔单列 -> 结构化 DataFrame"""
    df = pd.read_excel(RAW_DIR / "process_parameters.xlsx",
                       sheet_name="data", header=None, skiprows=1)
    raw = df[0].str.split(";", expand=True)
    raw.columns = FEATURES + ["quality"]
    raw = raw.apply(pd.to_numeric)
    # UCI 数据说明: quality 1/2 为不合格, 3/4 为合格
    raw["quality"] = (raw["quality"] >= 3).astype(int)
    raw["material"] = REAL_DATA_MATERIAL
    raw["defect_type"] = np.where(raw["quality"] == 1, "合格", "未知")
    raw["source"] = "real"
    return raw


# 各特征违规概率(熔体/模具温度与关键压力时间较易违规)
# 违规概率适当提高,保证每类缺陷有足够样本支撑模型学习决策边界
VIOL_RATES = {
    "melt_temp": 0.20, "mold_temp": 0.18,
    "time_to_fill": 0.12, "injection_pressure_peak": 0.12, "cycle_time": 0.12,
    "shot_volume": 0.05, "plasticizing_time": 0.05, "closing_force": 0.05,
    "clamp_force_peak": 0.05, "torque_peak": 0.05, "torque_mean": 0.05,
    "back_pressure_peak": 0.05, "screw_pos_end_hold": 0.05,
}


# 违规区深度(占允许范围跨度的比例): 温度类参数取值跨度大,
# 典型操作错误偏离更远,故深度更大;其余参数 30%
VIOL_DEPTH = {"melt_temp": 0.45, "mold_temp": 0.45}


def _sample_cond(mat_cfg: dict, key: str, violated: bool, any_violation: bool) -> float:
    """条件采样: 违规特征落在边界外违规区;非违规特征 70% 推荐区 / 30% 允许区。

    以单特征违规为主,保证"某参数越界 -> 不合格"的决策边界清晰可学;
    边界角落由非违规特征的 30% 允许区采样自然覆盖。
    """
    cfg = mat_cfg.get(key) or GLOBAL_RANGES[key]
    lo, hi = cfg["bounds"]
    rlo, rhi = cfg["rec"]
    span = hi - lo
    depth = VIOL_DEPTH.get(key, 0.3)
    if violated:  # 违规区: [lo-depth×跨度, lo) 或 (hi, hi+depth×跨度]
        if RNG.random() < 0.5:
            return float(RNG.uniform(lo - depth * span, lo))
        return float(RNG.uniform(hi, hi + depth * span))
    if RNG.random() < 0.7:  # 多数落在推荐区
        return float(RNG.uniform(rlo, rhi))
    return float(RNG.uniform(lo, hi))


def generate_synthetic() -> pd.DataFrame:
    """生成 7 种材料的合成数据, 带规则驱动的缺陷类型标签"""
    rows = []
    for mat in MATERIALS:
        cfg = MATERIALS[mat]
        for _ in range(N_SYN_PER_MATERIAL):
            flags = {k: RNG.random() < v for k, v in VIOL_RATES.items()}
            any_violation = any(flags.values())
            params = {k: _sample_cond(cfg, k, flags[k], any_violation)
                      for k in VIOL_RATES}
            defect = diagnose_params(params, mat)["defect_type"]
            quality = 1 if defect == "合格" else 0
            if RNG.random() < 0.02:  # 2% 标签噪声模拟检测误差
                quality = 1 - quality
                defect = "合格" if quality == 1 else defect
            row = dict(params, material=mat, quality=quality,
                       defect_type=defect, source="synthetic")
            rows.append(row)
    return pd.DataFrame(rows)


def build_dataset_meta(df: pd.DataFrame) -> dict:
    """生成数据集元信息: 各材料特征范围, 供后端默认值与优化约束使用"""
    meta = {"total": len(df), "by_material": {}, "by_defect": {}}
    for mat, g in df.groupby("material"):
        stats = {f: [round(float(g[f].min()), 2), round(float(g[f].max()), 2)]
                 for f in FEATURES}
        meta["by_material"][mat] = {
            "count": int(len(g)),
            "ok_rate": round(float(g["quality"].mean()), 3),
            "ranges": stats,
            "rec_ranges": {
                k: (MATERIALS[mat].get(k) or GLOBAL_RANGES[k])["rec"] for k in FEATURES
            },
        }
    for d, g in df.groupby("defect_type"):
        meta["by_defect"][d] = int(len(g))
    return meta


def generate_cypher() -> None:
    """由知识图谱 JSON 生成 Neo4j Cypher 导入脚本"""
    kg = json.loads(KG_FILE.read_text(encoding="utf-8"))
    lines = [
        "// 注塑工艺知识图谱 Neo4j 导入脚本(自动生成)",
        f"// 实体类型: {', '.join(kg['meta']['entity_types'])}",
        f"// 关系类型: {', '.join(kg['meta']['relation_types'])}",
        "",
        "// 1. 约束",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;",
        "",
        "// 2. 实体",
    ]
    for n in kg["nodes"]:
        props = ", ".join(f"{k}: '{v}'" for k, v in n["props"].items())
        lines.append(
            f"MERGE (:Entity {{id: '{n['id']}', name: '{n['name']}', "
            f"type: '{n['type']}', {props}}});"
        )
    lines += ["", "// 3. 关系"]
    for e in kg["edges"]:
        props = ", ".join(f"{k}: '{v}'" for k, v in e["props"].items())
        prop_str = f", {props}" if props else ""
        lines.append(
            f"MATCH (a:Entity {{id: '{e['from']}'}}), (b:Entity {{id: '{e['to']}'}}) "
            f"MERGE (a)-[:{e['rel']}{prop_str}]->(b);"
        )
    (PROCESSED_DIR / "knowledge_graph.cypher").write_text(
        "\n".join(lines), encoding="utf-8")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    real = parse_real_data()
    synth = generate_synthetic()
    df = pd.concat([real, synth], ignore_index=True)
    df.to_csv(PROCESSED_DIR / "dataset.csv", index=False, encoding="utf-8-sig")

    meta = build_dataset_meta(df)
    meta["real_rows"] = int((df["source"] == "real").sum())
    meta["synthetic_rows"] = int((df["source"] == "synthetic").sum())
    (PROCESSED_DIR / "dataset_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    generate_cypher()

    print(f"总样本: {len(df)} (真实 {meta['real_rows']} + 合成 {meta['synthetic_rows']})")
    print("\n合格率:");
    for mat, g in df.groupby("material"):
        print(f"  {mat}: {g['quality'].mean():.1%} ({len(g)} 条)")
    print("\n缺陷分布:")
    for d, c in df["defect_type"].value_counts().items():
        print(f"  {d}: {c}")
    print(f"\n输出: {PROCESSED_DIR / 'dataset.csv'}")
    print(f"      {PROCESSED_DIR / 'dataset_meta.json'}")
    print(f"      {PROCESSED_DIR / 'knowledge_graph.cypher'}")


if __name__ == "__main__":
    main()
