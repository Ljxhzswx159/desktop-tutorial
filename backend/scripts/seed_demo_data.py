"""演示数据播种:为看板/记录页生成近 14 天的模拟生产记录

运行: py -3.13 backend/scripts/seed_demo_data.py
"""
import datetime as dt
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/
from app.config import GLOBAL_RANGES, MATERIALS
from app.db import ProductionRecord, SessionLocal, init_db
from app.services.rule_diagnosis import diagnose

RNG = np.random.default_rng(7)
EQUIP = ["海天MA1200", "海天MA2500", "震雄SM120", "伊之密UN260"]
PRODUCTS = ["汽车内饰件", "电子外壳", "精密齿轮", "日用壳体"]


def gen_params(material: str, defect_rate: float) -> dict:
    """生成一组参数: defect_rate 概率落在违规区"""
    m = MATERIALS[material]
    params = {}
    for key, cfg in m.items():
        if key == "label":
            continue
        if RNG.random() < defect_rate / 4:  # 违规区
            lo, hi = cfg["bounds"]
            span = hi - lo
            params[key] = float(RNG.uniform(lo - 0.08 * span, lo)) \
                if RNG.random() < 0.5 else float(RNG.uniform(hi, hi + 0.08 * span))
        else:
            rlo, rhi = cfg["rec"]
            params[key] = float(RNG.uniform(rlo, rhi))
    for key, cfg in GLOBAL_RANGES.items():
        if RNG.random() < defect_rate / 5:
            lo, hi = cfg["bounds"]
            span = hi - lo
            params[key] = float(RNG.uniform(lo - 0.08 * span, lo)) \
                if RNG.random() < 0.5 else float(RNG.uniform(hi, hi + 0.08 * span))
        else:
            params[key] = float(RNG.uniform(*cfg["rec"]))
    return {k: round(float(v), 2) for k, v in params.items()}


def main() -> None:
    init_db()
    n = 0
    with SessionLocal() as db:
        # 删除旧演示数据后重建
        db.query(ProductionRecord).delete()
        for day_offset in range(13, -1, -1):
            day = dt.datetime.now() - dt.timedelta(days=day_offset)
            for _ in range(RNG.integers(3, 7)):
                material = str(RNG.choice(list(MATERIALS)))
                defect_rate = float(RNG.choice([0.05, 0.1, 0.25]))
                params = gen_params(material, defect_rate)
                diag = diagnose(params, material, rng=np.random.default_rng(0))
                quality = 1 if diag["defect_type"] == "合格" else 0
                db.add(ProductionRecord(
                    created_at=day.replace(
                        hour=int(RNG.integers(8, 18)), minute=int(RNG.integers(0, 60))),
                    product_type=str(RNG.choice(PRODUCTS)),
                    material=material,
                    equipment=str(RNG.choice(EQUIP)),
                    operator=f"操作员{RNG.integers(1, 5)}",
                    quality=quality,
                    defect_type="" if quality else diag["defect_type"],
                    source="manual",
                    note="试模记录" if quality == 0 else "",
                    **params,
                ))
                n += 1
        db.commit()
    print(f"已生成 {n} 条模拟生产记录(近14天)")


if __name__ == "__main__":
    main()
