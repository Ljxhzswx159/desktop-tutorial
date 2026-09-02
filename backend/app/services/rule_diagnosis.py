"""工艺规则缺陷诊断:基于领域知识(材料参数边界)的参数违规诊断。

与知识图谱模块配合:诊断出的缺陷类型可通过知识图谱检索诱因与对策。
数据预处理脚本(preprocess.py)复用同一套规则为合成数据打标签,
保证"训练标签规则"与"在线诊断规则"的一致性。
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import GLOBAL_RANGES, MATERIALS

# 缺陷规则严重度顺序(多条违规时取最靠前者)
RULE_ORDER = ["烧焦", "银纹", "缺料", "飞边", "熔接线", "缩痕", "翘曲变形"]


def diagnose(params: dict, material: str, rng: np.random.Generator | None = None) -> dict:
    """对一组工艺参数执行规则诊断。

    返回 {defect_type, violations: [{param, rule, severity}]}
    defect_type 为 '合格' 表示无违规。
    """
    if material not in MATERIALS:
        raise ValueError(f"未知材料: {material}")
    rng = rng or np.random.default_rng()
    m = MATERIALS[material]
    violations: list[dict] = []

    def check(param: str, lo: float, hi: float, defect: str, desc: str) -> None:
        v = params[param]
        if v > hi:
            violations.append({"param": param, "rule": desc, "defect": defect,
                               "severity": RULE_ORDER.index(defect)})
        elif v < lo:
            violations.append({"param": param, "rule": desc, "defect": defect,
                               "severity": RULE_ORDER.index(defect)})

    mb = m["melt_temp"]["bounds"]
    if params["melt_temp"] > mb[1]:
        violations.append({"param": "melt_temp",
                           "rule": f"熔体温度超过上限 {mb[1]}°C",
                           "defect": rng.choice(["银纹", "烧焦"], p=[0.55, 0.45]),
                           "severity": 0})
    check("melt_temp", mb[0], mb[1], "缺料",
          f"熔体温度低于下限 {mb[0]}°C")
    ob = m["mold_temp"]["bounds"]
    if params["mold_temp"] > ob[1]:
        violations.append({"param": "mold_temp",
                           "rule": f"模具温度超过上限 {ob[1]}°C", "defect": "缩痕",
                           "severity": RULE_ORDER.index("缩痕")})
    if params["mold_temp"] < ob[0]:
        violations.append({"param": "mold_temp",
                           "rule": f"模具温度低于下限 {ob[0]}°C", "defect": "熔接线",
                           "severity": RULE_ORDER.index("熔接线")})
    tb = m["time_to_fill"]["bounds"]
    if params["time_to_fill"] < tb[0]:
        violations.append({"param": "time_to_fill",
                           "rule": f"填充时间过快(<{tb[0]}s)", "defect": "银纹",
                           "severity": RULE_ORDER.index("银纹")})
    if params["time_to_fill"] > tb[1]:
        violations.append({"param": "time_to_fill",
                           "rule": f"填充时间过慢(>{tb[1]}s)", "defect": "熔接线",
                           "severity": RULE_ORDER.index("熔接线")})
    ib = m["injection_pressure_peak"]["bounds"]
    if params["injection_pressure_peak"] > ib[1]:
        violations.append({"param": "injection_pressure_peak",
                           "rule": f"注射压力超过上限 {ib[1]}bar", "defect": "飞边",
                           "severity": RULE_ORDER.index("飞边")})
    if params["injection_pressure_peak"] < ib[0]:
        violations.append({"param": "injection_pressure_peak",
                           "rule": f"注射压力低于下限 {ib[0]}bar", "defect": "缺料",
                           "severity": RULE_ORDER.index("缺料")})
    cb = m["cycle_time"]["bounds"]
    if params["cycle_time"] < cb[0]:
        violations.append({"param": "cycle_time",
                           "rule": f"循环时间不足(<{cb[0]}s),冷却不充分",
                           "defect": "翘曲变形", "severity": RULE_ORDER.index("翘曲变形")})
    sb = GLOBAL_RANGES["screw_pos_end_hold"]["bounds"]
    if params["screw_pos_end_hold"] < sb[0]:
        violations.append({"param": "screw_pos_end_hold",
                           "rule": f"保压结束螺杆位置过低(<{sb[0]}mm),补缩不足",
                           "defect": "缩痕", "severity": RULE_ORDER.index("缩痕")})

    if not violations:
        return {"defect_type": "合格", "violations": []}
    # 按严重度取首要缺陷,附带全部违规明细
    primary = min(violations, key=lambda v: v["severity"])["defect"]
    return {"defect_type": primary, "violations": violations}
