"""全局配置与领域常量定义。

特征定义与材料参数范围是数据预处理、模型训练、参数优化、知识图谱
各模块共享的领域知识,集中在此维护。
"""
from pathlib import Path

# ---------- 路径 ----------
ROOT_DIR = Path(__file__).resolve().parent.parent.parent          # keshe/
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = PROCESSED_DIR / "models"
KG_FILE = ROOT_DIR / "knowledge" / "kg_data.json"
DB_URL = f"sqlite:///{PROCESSED_DIR / 'injection.db'}"

# ---------- 工艺特征(与真实数据集字段一一对应) ----------
FEATURES: list[str] = [
    "melt_temp",                  # 熔体温度
    "mold_temp",                  # 模具温度
    "time_to_fill",               # 填充时间
    "plasticizing_time",          # 塑化时间
    "cycle_time",                 # 循环时间
    "closing_force",              # 合模力
    "clamp_force_peak",           # 合模力峰值
    "torque_peak",                # 扭矩峰值
    "torque_mean",                # 扭矩均值
    "back_pressure_peak",         # 背压峰值
    "injection_pressure_peak",    # 注射压力峰值
    "screw_pos_end_hold",         # 保压结束螺杆位置
    "shot_volume",                # 射胶量
]

FEATURE_LABELS = {
    "melt_temp": "熔体温度 (°C)",
    "mold_temp": "模具温度 (°C)",
    "time_to_fill": "填充时间 (s)",
    "plasticizing_time": "塑化时间 (s)",
    "cycle_time": "循环时间 (s)",
    "closing_force": "合模力 (kN)",
    "clamp_force_peak": "合模力峰值 (kN)",
    "torque_peak": "扭矩峰值 (Nm)",
    "torque_mean": "扭矩均值 (Nm)",
    "back_pressure_peak": "背压峰值 (bar)",
    "injection_pressure_peak": "注射压力峰值 (bar)",
    "screw_pos_end_hold": "保压结束螺杆位置 (mm)",
    "shot_volume": "射胶量 (cm³)",
}

# 缺陷类型(多分类模型标签,0 为合格)
DEFECT_TYPES = ["合格", "翘曲变形", "缩痕", "飞边", "银纹", "熔接线", "缺料", "烧焦"]

# ---------- 材料参数范围(领域知识,与 knowledge/kg_data.json 一致) ----------
# 每个材料给出: 推荐范围 (rec) 与允许范围 (bounds, 用于优化搜索空间)
MATERIALS = {
    "ABS": {
        "label": "ABS(丙烯腈-丁二烯-苯乙烯)",
        "melt_temp": {"rec": [215, 235], "bounds": [190, 250]},
        "mold_temp": {"rec": [55, 65], "bounds": [40, 80]},
        "time_to_fill": {"rec": [5.5, 7.5], "bounds": [4.5, 9]},
        "injection_pressure_peak": {"rec": [820, 950], "bounds": [760, 1000]},
        "cycle_time": {"rec": [60, 75], "bounds": [50, 85]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "PP": {
        "label": "PP(聚丙烯)",
        "melt_temp": {"rec": [220, 250], "bounds": [200, 280]},
        "mold_temp": {"rec": [35, 45], "bounds": [20, 80]},
        "time_to_fill": {"rec": [5, 7], "bounds": [4, 8.5]},
        "injection_pressure_peak": {"rec": [700, 830], "bounds": [650, 880]},
        "cycle_time": {"rec": [55, 70], "bounds": [45, 80]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "PC": {
        "label": "PC(聚碳酸酯)",
        "melt_temp": {"rec": [285, 305], "bounds": [270, 320]},
        "mold_temp": {"rec": [85, 95], "bounds": [70, 120]},
        "time_to_fill": {"rec": [8, 10], "bounds": [6.5, 12]},
        "injection_pressure_peak": {"rec": [880, 1010], "bounds": [820, 1060]},
        "cycle_time": {"rec": [65, 80], "bounds": [55, 90]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "PA66": {
        "label": "PA66(尼龙66)",
        "melt_temp": {"rec": [265, 280], "bounds": [260, 290]},
        "mold_temp": {"rec": [70, 80], "bounds": [60, 90]},
        "time_to_fill": {"rec": [7, 9], "bounds": [5.5, 10.5]},
        "injection_pressure_peak": {"rec": [840, 970], "bounds": [780, 1020]},
        "cycle_time": {"rec": [58, 72], "bounds": [48, 82]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "POM": {
        "label": "POM(聚甲醛)",
        "melt_temp": {"rec": [195, 210], "bounds": [180, 220]},
        "mold_temp": {"rec": [75, 85], "bounds": [60, 100]},
        "time_to_fill": {"rec": [6, 8], "bounds": [5, 9.5]},
        "injection_pressure_peak": {"rec": [780, 910], "bounds": [720, 960]},
        "cycle_time": {"rec": [58, 72], "bounds": [48, 82]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "PS": {
        "label": "PS(聚苯乙烯)",
        "melt_temp": {"rec": [200, 220], "bounds": [180, 240]},
        "mold_temp": {"rec": [35, 45], "bounds": [20, 60]},
        "time_to_fill": {"rec": [4.5, 6.5], "bounds": [3.5, 8]},
        "injection_pressure_peak": {"rec": [680, 810], "bounds": [630, 860]},
        "cycle_time": {"rec": [52, 66], "bounds": [42, 78]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
    "PMMA": {
        "label": "PMMA(聚甲基丙烯酸甲酯)",
        "melt_temp": {"rec": [225, 245], "bounds": [210, 260]},
        "mold_temp": {"rec": [60, 70], "bounds": [50, 80]},
        "time_to_fill": {"rec": [7, 9], "bounds": [5.5, 10.5]},
        "injection_pressure_peak": {"rec": [800, 930], "bounds": [740, 980]},
        "cycle_time": {"rec": [60, 74], "bounds": [50, 84]},
        "shot_volume": {"rec": [16, 20], "bounds": [14, 23]},
    },
}

# 真实数据集材料归类(原数据集未标注材料牌号,按 ABS 工艺处理)
REAL_DATA_MATERIAL = "ABS"

# 其他机器参数全局典型范围(合成数据与优化搜索共用)
GLOBAL_RANGES = {
    "plasticizing_time": {"rec": [2.8, 5.0], "bounds": [2.5, 6.5]},
    "closing_force": {"rec": [870, 930], "bounds": [840, 1000]},
    "clamp_force_peak": {"rec": [890, 950], "bounds": [860, 1020]},
    "torque_peak": {"rec": [95, 140], "bounds": [85, 175]},
    "torque_mean": {"rec": [80, 120], "bounds": [70, 150]},
    "back_pressure_peak": {"rec": [140, 160], "bounds": [125, 180]},
    "screw_pos_end_hold": {"rec": [8.3, 9.2], "bounds": [7.0, 12.0]},
}

# 产品类型(演示用)
PRODUCT_TYPES = ["汽车内饰件", "电子外壳", "精密齿轮", "医疗耗材", "日用壳体"]

# 设备型号(演示用,对应知识图谱设备实体)
EQUIPMENTS = ["海天MA1200", "海天MA2500", "震雄SM120", "伊之密UN260"]
