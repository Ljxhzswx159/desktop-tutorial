"""知识图谱服务:注塑工艺知识图谱(实体/关系)的加载与检索

数据源: knowledge/kg_data.json(教材知识+专家经验整理)
实体类型: 材料、设备、参数、缺陷、对策、工艺规则
关系类型: 适用于、影响、解决、约束

支持:
  1. 关键词检索(含自然语言别名映射)与一跳邻居子图;
  2. 缺陷根因分析: (参数)-[影响]->(缺陷)<-[解决]-(对策) 两跳子图;
  3. 材料工艺画像: 材料 + 适用设备 + 受约束参数 + 相关工艺规则;
  4. 全图导出(前端可视化)。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from app.config import KG_FILE

# 自然语言别名 -> 实体名/类型(支持口语化查询)
ALIASES = {
    "变形": "翘曲变形", "弯": "翘曲变形", "翘": "翘曲变形", "扭曲": "翘曲变形",
    "凹陷": "缩痕", "缩水": "缩痕", "缩坑": "缩痕",
    "毛边": "飞边", "披锋": "飞边", "溢料": "飞边", "溢胶": "飞边",
    "白纹": "银纹", "银丝": "银纹", "料花": "银纹",
    "结合线": "熔接线", "接缝线": "熔接线", "汇合线": "熔接线",
    "打不满": "缺料", "短射": "缺料", "充不满": "缺料",
    "糊": "烧焦", "焦": "烧焦", "发黄": "烧焦", "发黑": "烧焦",
    "裂纹": "裂纹", "开裂": "裂纹",
    "尺寸": "尺寸偏差", "超差": "尺寸偏差",
    "模温": "模具温度", "料温": "熔体温度", "射压": "注射压力",
    "注射速度": "注射速度", "保压": "保压压力", "冷却": "冷却时间",
    "温度": "熔体温度", "压力": "注射压力",
    "亚克力": "PMMA", "尼龙": "PA66", "聚碳酸酯": "PC",
    "聚丙烯": "PP", "聚苯乙烯": "PS", "聚甲醛": "POM",
}

# 关键词 -> 实体类型过滤(检索时按类型加权)
TYPE_KEYWORDS = {
    "缺陷": "缺陷", "问题": "缺陷", "不良": "缺陷",
    "材料": "材料", "设备": "设备", "机器": "设备", "注塑机": "设备",
    "参数": "参数", "温度": "参数", "压力": "参数", "时间": "参数",
    "对策": "对策", "解决": "对策", "怎么办": "对策", "措施": "对策",
    "规则": "工艺规则",
}


class KnowledgeGraph:
    """轻量级内存图存储 + 检索(可平替为 Neo4j,见 knowledge_graph.cypher)"""

    def __init__(self) -> None:
        data = json.loads(KG_FILE.read_text(encoding="utf-8"))
        self.nodes: dict[str, dict] = {n["id"]: n for n in data["nodes"]}
        self.edges: list[dict] = data["edges"]
        # 邻接表: id -> [(neighbor_id, rel, edge_props)]
        self.adj: dict[str, list[tuple[str, str, dict]]] = {
            nid: [] for nid in self.nodes
        }
        for e in self.edges:
            self.adj[e["from"]].append((e["to"], e["rel"], e["props"]))
            self.adj[e["to"]].append((e["from"], e["rel"], e["props"]))

    # ---------- 基础查询 ----------

    def get(self, node_id: str) -> dict | None:
        return self.nodes.get(node_id)

    def neighbors(self, node_id: str) -> list[dict]:
        """一跳邻居(含关系方向信息)"""
        out = []
        for nid, rel, props in self.adj.get(node_id, []):
            node = self.nodes[nid]
            out.append({"node": {"id": nid, "name": node["name"],
                                 "type": node["type"], "props": node["props"]},
                        "rel": rel, "props": props})
        return out

    def subgraph(self, center_id: str, depth: int = 1) -> dict:
        """以某实体为中心导出 depth 跳子图(前端可视化)"""
        nodes, edges = {}, []
        frontier, visited = {center_id}, {center_id}
        for _ in range(depth):
            nxt = set()
            for nid in frontier:
                for eid, rel, props in self.adj.get(nid, []):
                    edge_key = tuple(sorted([nid, eid]) + [rel])
                    edges.append({"source": nid, "target": eid, "rel": rel,
                                  "props": props, "key": str(edge_key)})
                    if eid not in visited:
                        visited.add(eid)
                        nxt.add(eid)
            frontier = nxt
        # 去重边
        uniq_edges = {e["key"]: e for e in edges}
        for nid in visited:
            n = self.nodes[nid]
            nodes[nid] = {"id": nid, "name": n["name"], "type": n["type"],
                          "props": n["props"]}
        return {"nodes": list(nodes.values()),
                "edges": list(uniq_edges.values())}

    # ---------- 业务检索 ----------

    def _match_entity(self, text: str) -> str | None:
        """文本 -> 实体 id 匹配(精确 > 名称包含 > 别名)"""
        if text in self.nodes:
            return text
        for nid, n in self.nodes.items():
            if n["name"] == text:
                return nid
        # 子串匹配: "缺料" 命中 "缺料(短射)", 也支持 "翘曲" 命中 "翘曲变形"
        for nid, n in self.nodes.items():
            if text in n["name"]:
                return nid
        if text in ALIASES:
            target = ALIASES[text]
            for nid, n in self.nodes.items():
                if n["name"] == target:
                    return nid
        return None

    def search(self, query: str, limit: int = 10) -> dict:
        """关键词/自然语言检索: 返回命中的实体及一跳邻居"""
        q = query.strip()
        results = []
        seen = set()

        # 1. 别名/名称精确命中优先
        exact = self._match_entity(q)
        if exact:
            results.append({"node": self.nodes[exact], "score": 1.0})
            seen.add(exact)

        # 2. 类型过滤(缺陷/材料/设备/参数/对策/规则)
        type_hint = None
        for kw, t in TYPE_KEYWORDS.items():
            if kw in q:
                type_hint = t
                break

        # 3. 名称/属性包含匹配
        for nid, n in self.nodes.items():
            if nid in seen:
                continue
            score = 0.0
            if q and q in n["name"]:
                score += 1.0
            prop_text = " ".join(f"{k}{v}" for k, v in n["props"].items())
            if q and q in prop_text:
                score += 0.5
            if type_hint and n["type"] == type_hint:
                score += 0.3
            # 别名词出现在属性中
            for alias, target in ALIASES.items():
                if alias in q and n["name"] == target:
                    score += 0.8
                    break
            if score > 0:
                results.append({"node": n, "score": round(score, 2)})

        # 4. 查询中出现的缺陷(名称子串或别名) -> 附带根因分析
        results.sort(key=lambda r: -r["score"])
        results = results[:limit]
        for r in results:
            r["neighbors"] = self.neighbors(r["node"]["id"])
        defect_in_query: str | None = None
        if exact and self.nodes[exact]["type"] == "缺陷":
            defect_in_query = self.nodes[exact]["name"]
        if defect_in_query is None:  # 自然语言整句查询: 缺陷名与查询互为子串
            for n in self.nodes.values():
                if n["type"] == "缺陷" and (n["name"] in q or q in n["name"]):
                    defect_in_query = n["name"]
                    break
        if defect_in_query is None:  # 别名匹配
            for alias, target in ALIASES.items():
                if alias in q:
                    for n in self.nodes.values():
                        if n["name"] == target and n["type"] == "缺陷":
                            defect_in_query = target
                            break
                    break
        analysis = (self.defect_analysis(defect_in_query)
                    if defect_in_query else None)
        return {"query": query, "results": results, "defect_analysis": analysis}

    def defect_analysis(self, defect_name: str) -> dict:
        """缺陷根因分析: 影响参数(原因) + 解决对策

        关系方向: (参数)-[影响]->(缺陷), (对策)-[解决]->(缺陷)
        """
        did = self._match_entity(defect_name)
        if not did or self.nodes[did]["type"] != "缺陷":
            return {"defect": defect_name, "causes": [], "countermeasures": []}
        causes, countermeasures = [], []
        for e in self.edges:
            if e["to"] == did and e["rel"] == "影响":
                n = self.nodes[e["from"]]
                causes.append({"param": n["name"], "detail": e["props"].get("方向", "")})
            if e["to"] == did and e["rel"] == "解决":
                n = self.nodes[e["from"]]
                countermeasures.append({"action": n["name"],
                                        "detail": n["props"].get("操作要点", "")})
        return {"defect": defect_name, "causes": causes,
                "countermeasures": countermeasures,
                "subgraph": self.subgraph(did, depth=1)}

    def material_profile(self, material: str) -> dict:
        """材料工艺画像: 材料 + 适用设备 + 相关工艺规则(规则为通用注塑规则)"""
        mid = self._match_entity(material)
        if not mid:
            return {"material": material, "equipments": [], "rules": [],
                    "node": None}
        node = self.nodes[mid]
        # "适用于" 关系方向为 设备->材料, 取另一端(设备)节点
        equipments = [
            self.nodes[e["from"] if e["to"] == mid else e["to"]]
            for e in self.edges
            if e["rel"] == "适用于" and mid in (e["from"], e["to"])
        ]
        rules = [n for n in self.nodes.values() if n["type"] == "工艺规则"]
        return {"material": material, "node": node,
                "equipments": equipments, "rules": rules}

    def full_graph(self) -> dict:
        """全图导出"""
        return {"nodes": [{"id": nid, "name": n["name"], "type": n["type"],
                           "props": n["props"]} for nid, n in self.nodes.items()],
                "edges": [{"source": e["from"], "target": e["to"],
                           "rel": e["rel"], "props": e["props"]}
                          for e in self.edges]}


# 模块级单例
kg = KnowledgeGraph()
