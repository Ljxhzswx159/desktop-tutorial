"""参数优化模块:NSGA-II 多目标遗传算法(DEAP 实现)

优化目标:
  1. 最大化质量合格概率(由质量预测模型评估)
  2. 最小化能耗代理指标(循环时间 + 0.3×熔体温度)

约束:各工艺参数限定在该材料允许范围(来自知识图谱领域知识)内。

搜索得到 Pareto 最优解集,再综合两目标给出推荐解。
"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from deap import algorithms, base, creator, tools

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import FEATURES, GLOBAL_RANGES, MATERIALS

# 能耗代理: 循环时间 + 0.3×熔体温度(加热能耗)
ENERGY_W = {"cycle_time": 1.0, "melt_temp": 0.3}


def _bounds(material: str) -> list[tuple[float, float]]:
    """按特征顺序返回该材料的搜索边界"""
    bounds = []
    for f in FEATURES:
        cfg = MATERIALS[material].get(f) or GLOBAL_RANGES[f]
        bounds.append(tuple(float(v) for v in cfg["bounds"]))
    return bounds


def energy(params: dict) -> float:
    """能耗代理指标(越小越好)"""
    return params["cycle_time"] + ENERGY_W["melt_temp"] * params["melt_temp"]


class NSGA2Optimizer:
    """基于质量预测模型的工艺参数多目标优化器"""

    def __init__(self, quality_model, material: str, random_seed: int = 2026):
        self.material = material
        self.model = quality_model
        self.bounds = _bounds(material)
        # 预构造一行 NumPy 模板,评估时仅填充 13 个特征值(避免反复构造 DataFrame)
        self.cols = list(quality_model.feature_names_in_)
        self.template = np.zeros((1, len(self.cols)))
        self.template[0, self.cols.index(f"mat_{material}")] = 1

        creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0))
        creator.create("Individual", list, fitness=creator.FitnessMulti)
        random.seed(random_seed)  # DEAP 算子使用 Python random 模块
        self.toolbox = base.Toolbox()

        for i, (lo, hi) in enumerate(self.bounds):
            self.toolbox.register(f"attr_{i}", np.random.uniform, lo, hi)
        self.toolbox.register(
            "individual",
            tools.initCycle, creator.Individual,
            [getattr(self.toolbox, f"attr_{i}") for i in range(len(FEATURES))],
            n=1,
        )
        self.toolbox.register("population", tools.initRepeat, list,
                              self.toolbox.individual)
        self.toolbox.register("evaluate", self._evaluate)
        self.toolbox.register("mate", tools.cxSimulatedBinaryBounded,
                              eta=15.0, low=[b[0] for b in self.bounds],
                              up=[b[1] for b in self.bounds])
        self.toolbox.register("mutate", tools.mutPolynomialBounded,
                              eta=20.0, low=[b[0] for b in self.bounds],
                              up=[b[1] for b in self.bounds],
                              indpb=0.35)
        self.toolbox.register("select", tools.selNSGA2)

    def _evaluate(self, ind) -> tuple[float, float]:
        """个体适应度: (合格概率, 能耗)"""
        row = self.template.copy()
        for i, v in enumerate(ind):
            row[0, self.cols.index(FEATURES[i])] = v
        proba = float(self.model.predict_proba(row)[0, 1])
        return proba, energy({f: float(v) for f, v in zip(FEATURES, ind)})

    def optimize(self, pop_size: int = 60, n_gen: int = 25,
                 cx_pb: float = 0.8, mut_pb: float = 0.2) -> list[dict]:
        """运行 NSGA-II,返回 Pareto 前沿(按合格概率降序)"""
        pop = self.toolbox.population(n=pop_size)
        # 初始种群统计(仅用于日志)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("avg", lambda v: (np.mean([x[0] for x in v]),
                                         np.mean([x[1] for x in v])))
        stats.register("max", lambda v: (np.max([x[0] for x in v]),
                                         np.min([x[1] for x in v])))
        pop, _ = algorithms.eaMuPlusLambda(
            pop, self.toolbox, mu=pop_size, lambda_=pop_size,
            cxpb=cx_pb, mutpb=mut_pb, ngen=n_gen, stats=stats, verbose=False)

        pareto = tools.sortNondominated(pop, k=len(pop), first_front_only=True)[0]
        front = []
        for ind in pareto:
            params = {f: round(float(v), 2) for f, v in zip(FEATURES, ind)}
            front.append({
                "params": params,
                "quality_prob": round(float(ind.fitness.values[0]), 4),
                "energy": round(float(ind.fitness.values[1]), 2),
            })
        # 去重并按合格概率降序
        seen, unique = set(), []
        for s in front:
            key = tuple(s["params"].values())
            if key not in seen:
                seen.add(key)
                unique.append(s)
        unique.sort(key=lambda s: -s["quality_prob"])
        return unique

    def recommend(self, front: list[dict]) -> dict:
        """从 Pareto 前沿中挑选推荐解:
        合格概率 ≥ 前沿最高值的 99.5% 中选能耗最低者(质量优先、兼顾能耗)"""
        if not front:
            raise RuntimeError("优化未产生有效解")
        best_q = front[0]["quality_prob"]
        candidates = [s for s in front if s["quality_prob"] >= best_q - 0.005]
        return min(candidates, key=lambda s: s["energy"])
