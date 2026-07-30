import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

import networkx as nx
from networkx.algorithms import community
import numpy as np
import requests

from config import KNOWLEDGE_BASE_CONFIG

try:
    import igraph as ig
    import leidenalg

    HAVE_LEIDEN = True
except ImportError:  # pragma: no cover - optional dependency
    HAVE_LEIDEN = False


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOGGER = logging.getLogger("events-network")

DEFAULT_EMBEDDING_CONFIG = {
    "url": KNOWLEDGE_BASE_CONFIG["embedding_url"],
    "model": KNOWLEDGE_BASE_CONFIG["embedding_model"],
    "apiType": "vllm",
    "timeout": 60,
    "dimension": 2560,
    "batchSize": 16,
}


def resolve_embedding_endpoint(url: str) -> str:
    if not url:
        raise ValueError("Embedding 鏈嶅姟鍦板潃涓嶈兘涓虹┖")
    trimmed = url.strip().rstrip("/")
    parsed = urlparse(trimmed)
    path = parsed.path or ""
    normalized_path = path.rstrip("/")
    if normalized_path.endswith("/embeddings") or normalized_path.endswith("/embedding"):
        return trimmed
    if normalized_path.endswith("/v1"):
        return f"{trimmed}/embeddings"
    if normalized_path == "":
        return f"{trimmed}/v1/embeddings"
    return trimmed


DEFAULT_COLORS = [
    "#5B8FF9",
    "#5AD8A6",
    "#5D7092",
    "#F6BD16",
    "#E8684A",
    "#6DC8EC",
    "#9270CA",
    "#FF9D4D",
    "#269A99",
    "#FF99C3",
]


def ensure_str_list(value: Optional[Iterable]) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def load_events(path: str, source_type: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as handle:
        raw_items = json.load(handle)

    events: List[Dict] = []
    for index, item in enumerate(raw_items):
        event_id = str(
            item.get("event_id")
            or item.get("id")
            or f"{source_type[:3]}-{index:05d}"
        )

        details = {
            "summary": (item.get("description") or "").strip(),
            "economyImpact": (item.get("economy_impact") or "").strip(),
            "internalImpact": item.get("internal_impact"),
            "origin": item.get("origin"),
            "source": item.get("source"),
        }

        events.append(
            {
                "id": event_id,
                "name": (item.get("event_name") or "").strip() or f"浜嬩欢 {index + 1}",
                "time": (item.get("time") or "").strip(),
                "location": (item.get("location") or "").strip(),
                "sourceType": source_type,
                "category": (item.get("type") or item.get("category") or "").strip(),
                "people": ensure_str_list(item.get("people")),
                "equipment": ensure_str_list(item.get("equipment")),
                "tags": ensure_str_list(item.get("tags")),
                "keywords": ensure_str_list(item.get("keywords")),
                "details": details,
            }
        )
    return events


def build_embedding_prompt(event: Dict) -> str:
    segments = [
        event.get("name", ""),
        event.get("category", ""),
        event.get("time", ""),
        event.get("location", ""),
        " ".join(event.get("people", [])),
        " ".join(event.get("equipment", [])),
        event.get("details", {}).get("summary", ""),
        event.get("details", {}).get("economyImpact", ""),
    ]
    extra = event.get("tags", []) + event.get("keywords", [])
    if extra:
        segments.append(" ".join(extra))
    return " ".join(part for part in segments if part)


def chunked(items: List[str], size: int) -> Iterator[List[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def deterministic_embedding(text: str, dim: int) -> List[float]:
    digest = hashlib.sha1(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = np.random.default_rng(seed)
    vector = rng.normal(size=dim)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector.tolist()
    return (vector / norm).tolist()


def fetch_embeddings(
    texts: List[str],
    url: str,
    model_name: str,
    timeout: int,
    batch_size: int,
    expected_dim: int,
) -> Tuple[np.ndarray, int]:
    results: List[List[float]] = []
    detected_dim: Optional[int] = None
    headers = {"Content-Type": "application/json"}

    for batch in chunked(texts, batch_size):
        payload = {
            "input": batch,
            "model": model_name,
            "encoding_format": "float",
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            embeddings = [item["embedding"] for item in data.get("data", [])]
            if len(embeddings) != len(batch):
                raise ValueError("embedding count mismatch")
            for vector in embeddings:
                vector_len = len(vector)
                if detected_dim is None:
                    detected_dim = vector_len
                    if detected_dim != expected_dim:
                        LOGGER.warning(
                            "Embedding 维度与期望不同：expected=%d, detected=%d。自动以服务返回为准。",
                            expected_dim,
                            detected_dim,
                        )
                elif vector_len != detected_dim:
                    raise ValueError(
                        f"embedding dimension mismatch within batch: expected {detected_dim}, got {vector_len}"
                    )
            results.extend(embeddings)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("embedding request failed, fallback to deterministic: %s", exc)
            target_dim = detected_dim or expected_dim
            for text_item in batch:
                results.append(deterministic_embedding(text_item, target_dim))
            if detected_dim is None:
                detected_dim = target_dim

    final_dim = detected_dim or expected_dim
    return np.array(results, dtype=np.float32), final_dim


def cosine_similarity(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12
    normalized = matrix / norms
    return normalized @ normalized.T


def build_semantic_edges(
    nodes: List[Dict],
    sim_matrix: np.ndarray,
    threshold: float,
    top_k: int,
) -> Dict[Tuple[str, str], Dict]:
    edge_map: Dict[Tuple[str, str], Dict] = {}
    if not nodes:
        return edge_map

    node_ids = [node["id"] for node in nodes]

    for idx, node_id in enumerate(node_ids):
        sims = sim_matrix[idx]
        sorted_indices = np.argsort(-sims)
        added = 0
        for neighbor_idx in sorted_indices[1:]:
            similarity = float(sims[neighbor_idx])
            if similarity < threshold or added >= top_k:
                break
            other_id = node_ids[neighbor_idx]
            key = tuple(sorted((node_id, other_id)))
            edge = edge_map.setdefault(
                key,
                {
                    "source": key[0],
                    "target": key[1],
                    "weight": similarity,
                    "similarity": similarity,
                    "kinds": {"semantic"},
                    "overlap": {"people": set(), "equipment": set()},
                },
            )
            edge["weight"] = max(edge["weight"], similarity)
            edge["similarity"] = max(edge["similarity"], similarity)
            edge["kinds"].add("semantic")
            added += 1

    return edge_map


def build_attribute_edges(
    nodes: List[Dict],
    edge_map: Dict[Tuple[str, str], Dict],
    base_weight: float,
) -> None:
    people_index: Dict[str, List[str]] = defaultdict(list)
    equipment_index: Dict[str, List[str]] = defaultdict(list)

    for node in nodes:
        for person in node.get("people", []):
            people_index[person].append(node["id"])
        for equip in node.get("equipment", []):
            equipment_index[equip].append(node["id"])

    def add_edges(index: Dict[str, List[str]], kind: str, key: str) -> None:
        for label, node_ids in index.items():
            if len(node_ids) < 2:
                continue
            for src, dst in combinations(sorted(node_ids), 2):
                edge_key = (src, dst)
                edge = edge_map.setdefault(
                    edge_key,
                    {
                        "source": src,
                        "target": dst,
                        "weight": base_weight,
                        "similarity": None,
                        "kinds": set(),
                        "overlap": {"people": set(), "equipment": set()},
                    },
                )
                edge["kinds"].add(kind)
                edge["overlap"][key].add(label)
                overlap_count = len(edge["overlap"][key])
                edge["weight"] = max(edge["weight"], base_weight + overlap_count * 0.05)

    add_edges(people_index, "shared_people", "people")
    add_edges(equipment_index, "shared_equipment", "equipment")


def ensure_cross_source_links(
    nodes: List[Dict],
    sim_matrix: np.ndarray,
    edge_map: Dict[Tuple[str, str], Dict],
    min_similarity: float = 0.45,
    boost: float = 1.1,
) -> None:
    id_to_index = {node["id"]: idx for idx, node in enumerate(nodes)}
    node_lookup = {node["id"]: node for node in nodes}
    adjacency: Dict[str, set] = defaultdict(set)
    for (src, dst), edge in edge_map.items():
        adjacency[src].add(dst)
        adjacency[dst].add(src)

    external_indices = [idx for idx, node in enumerate(nodes) if node.get("sourceType") == "external"]
    if not external_indices:
        return

    for node in nodes:
        if node.get("sourceType") != "internal":
            continue
        node_id = node["id"]
        neighbors = adjacency.get(node_id, set())
        if any(node_lookup[n_id].get("sourceType") == "external" for n_id in neighbors):
            continue
        idx = id_to_index[node_id]
        candidates = sorted(
            ((sim_matrix[idx, j], nodes[j]["id"]) for j in external_indices if nodes[j]["id"] != node_id),
            key=lambda item: item[0],
            reverse=True,
        )
        if not candidates:
            continue
        for similarity, external_id in candidates[:2]:
            if similarity <= 0:
                similarity = min_similarity
            weight = max(similarity, min_similarity) * boost
            key = tuple(sorted((node_id, external_id)))
            edge = edge_map.setdefault(
                key,
                {
                    "source": key[0],
                    "target": key[1],
                    "weight": weight,
                    "similarity": similarity,
                    "kinds": {"semantic_boost"},
                    "overlap": {"people": set(), "equipment": set()},
                },
            )
            edge["weight"] = max(edge.get("weight", 0.0), weight)
            if edge.get("similarity") is None:
                edge["similarity"] = similarity
            else:
                edge["similarity"] = max(edge["similarity"], similarity)
            kinds = edge.get("kinds")
            if isinstance(kinds, set):
                kinds.add("semantic_boost")
            adjacency[node_id].add(external_id)
            adjacency[external_id].add(node_id)


def apply_source_weighting(
    edge_map: Dict[Tuple[str, str], Dict],
    node_lookup: Dict[str, Dict],
    cross_boost: float = 1.4,
    external_penalty: float = 0.85,
    internal_penalty: float = 0.25,  # 进一步降低内部事件连接权重
) -> None:
    for edge in edge_map.values():
        src_type = node_lookup[edge["source"]].get("sourceType")
        dst_type = node_lookup[edge["target"]].get("sourceType")
        if src_type == dst_type == "internal":
            factor = internal_penalty  # 大幅降低内部事件之间的连接权重
        elif src_type == dst_type == "external":
            factor = external_penalty
        else:
            factor = cross_boost
        edge["weight"] *= factor
        edge["weight"] = max(0.05, min(edge["weight"], 3.0))
        if edge.get("similarity") is not None:
            edge["similarity"] *= factor
            edge["similarity"] = max(0.0, min(edge["similarity"], 3.0))
def normalize_edges(edge_map: Dict[Tuple[str, str], Dict]) -> List[Dict]:
    links: List[Dict] = []
    for edge in edge_map.values():
        overlap = {
            "people": sorted(edge["overlap"]["people"]),
            "equipment": sorted(edge["overlap"]["equipment"]),
        }
        links.append(
            {
                "source": edge["source"],
                "target": edge["target"],
                "weight": round(float(edge["weight"]), 4),
                "similarity": None
                if edge.get("similarity") is None
                else round(float(edge["similarity"]), 4),
                "kinds": sorted(edge["kinds"]),
                "overlap": overlap,
            }
        )
    return links


def compute_network_metrics(nodes: List[Dict], links: List[Dict]) -> Tuple[nx.Graph, Dict[str, Dict]]:
    graph = nx.Graph()
    for node in nodes:
        graph.add_node(node["id"])
    for link in links:
        graph.add_edge(link["source"], link["target"], weight=link.get("weight", 1.0))

    metrics: Dict[str, Dict] = {}
    if not graph.number_of_nodes():
        return graph, metrics

    degree_dict = dict(graph.degree())
    strength_dict = dict(graph.degree(weight="weight"))
    betweenness_dict = nx.betweenness_centrality(graph, weight="weight", normalized=True)
    pagerank_dict = nx.pagerank(graph, weight="weight", alpha=0.85) if graph.number_of_edges() else {}

    for node in nodes:
        node_id = node["id"]
        metrics[node_id] = {
            "degree": degree_dict.get(node_id, 0),
            "strength": round(strength_dict.get(node_id, 0.0), 4),
            "betweenness": round(betweenness_dict.get(node_id, 0.0), 6),
            "pagerank": round(pagerank_dict.get(node_id, 0.0), 6),
        }

    return graph, metrics


def _graph_to_igraph(graph: nx.Graph):
    nodes = list(graph.nodes())
    index = {node_id: idx for idx, node_id in enumerate(nodes)}
    edges = []
    weights = []
    for u, v, data in graph.edges(data=True):
        edges.append((index[u], index[v]))
        weights.append(float(data.get("weight", 1.0)))
    g = ig.Graph(len(nodes), edges)
    g.es["weight"] = weights
    g.vs["name"] = nodes
    return g


def leiden_partition(graph: nx.Graph, resolution: float) -> List[set]:
    if not HAVE_LEIDEN:
        raise RuntimeError("Leiden clustering requested but igraph/leidenalg is not available")
    if graph.number_of_edges() == 0:
        return [{node} for node in graph.nodes()]
    g = _graph_to_igraph(graph)
    partition = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        weights="weight",
        resolution_parameter=resolution,
    )
    return [set(g.vs[vertex]["name"] for vertex in part) for part in partition]


def louvain_partition(graph: nx.Graph, resolution: float) -> List[set]:
    if graph.number_of_edges() == 0:
        return [{node} for node in graph.nodes()]
    if hasattr(community, "louvain_communities"):
        communities = community.louvain_communities(graph, weight="weight", resolution=resolution, seed=42)
    else:
        communities = community.greedy_modularity_communities(graph, weight="weight")
    return [set(comm) for comm in communities]


def greedy_partition(graph: nx.Graph) -> List[set]:
    if graph.number_of_edges() == 0:
        return [{node} for node in graph.nodes()]
    return [set(comm) for comm in community.greedy_modularity_communities(graph, weight="weight")]


def detect_clusters(graph: nx.Graph, resolution: float, method: str) -> List[set]:
    method = (method or "leiden").lower()
    if method == "leiden":
        if HAVE_LEIDEN:
            return leiden_partition(graph, resolution)
        LOGGER.warning("Leiden requested but igraph/leidenalg not installed; falling back to Louvain")
        method = "louvain"
    if method == "louvain":
        return louvain_partition(graph, resolution)
    if method == "greedy":
        return greedy_partition(graph)
    LOGGER.warning("Unknown clustering method %s, defaulting to Louvain", method)
    return louvain_partition(graph, resolution)


def summarise_cluster(
    members: set,
    node_lookup: Dict[str, Dict],
    graph: nx.Graph,
    color: str,
    cluster_id: int,
) -> Dict:
    node_list = [node_lookup[node_id] for node_id in members]
    subgraph = graph.subgraph(members)
    edge_weights = [data.get("weight", 1.0) for *_, data in subgraph.edges(data=True)]

    people_counter = Counter()
    equipment_counter = Counter()
    for node in node_list:
        people_counter.update(node.get("people", []))
        equipment_counter.update(node.get("equipment", []))

    source_counter = Counter(node.get("sourceType", "unknown") for node in node_list)
    representative = max(
        node_list,
        key=lambda node: node.get("metrics", {}).get("pagerank", 0.0),
        default=node_list[0] if node_list else None,
    )

    density = (
        2 * subgraph.number_of_edges() / (len(members) * (len(members) - 1))
        if len(members) > 1
        else 0.0
    )
    average_weight = float(sum(edge_weights) / len(edge_weights)) if edge_weights else 0.0

    return {
        "id": cluster_id,
        "label": f"cluster-{cluster_id + 1}",
        "size": len(members),
        "density": round(density, 4),
        "averageWeight": round(average_weight, 4),
        "topPeople": [name for name, _ in people_counter.most_common(3)],
        "topEquipment": [name for name, _ in equipment_counter.most_common(3)],
        "representative": representative["id"] if representative else None,
        "color": color,
        "sourceMix": dict(source_counter),
    }


def validate_cluster_uniqueness(communities: List[set]) -> Tuple[bool, set]:
    """
    验证聚类中节点的唯一性
    
    Returns:
        Tuple[bool, set]: (是否唯一, 重复节点集合)
    """
    all_nodes = set()
    duplicates = set()
    
    for cluster in communities:
        intersection = all_nodes & cluster
        if intersection:
            duplicates.update(intersection)
        all_nodes.update(cluster)
    
    is_unique = len(duplicates) == 0
    return is_unique, duplicates


def ensure_unique_clusters(communities: List[set], min_size: int = 3) -> Tuple[List[set], set]:
    """
    确保一个事件只出现在一个聚类中，并过滤掉太小的聚类
    
    Returns:
        Tuple[List[set], set]: (唯一聚类列表, 已分配节点集合)
    """
    # 跟踪已经分配的节点
    assigned_nodes = set()
    unique_clusters = []

    # 按聚类大小排序，优先处理大聚类
    sorted_communities = sorted(communities, key=lambda x: len(x), reverse=True)

    for members in sorted_communities:
        if len(members) < min_size:
            continue  # 跳过太小的聚类

        # 只保留尚未分配的节点
        available_members = members - assigned_nodes

        if len(available_members) >= min_size:
            unique_clusters.append(available_members)
            assigned_nodes.update(available_members)
    
    # 验证节点唯一性
    is_unique, duplicates = validate_cluster_uniqueness(unique_clusters)
    if not is_unique:
        LOGGER.error("聚类唯一性验证失败! 发现 %d 个重复节点: %s", len(duplicates), list(duplicates)[:10])
    else:
        LOGGER.debug("聚类唯一性验证通过: %d 个聚类, %d 个节点", len(unique_clusters), len(assigned_nodes))
    
    return unique_clusters, assigned_nodes


def refine_clusters(communities: List[set], graph: nx.Graph, max_size: int, resolution: float, method: str) -> Tuple[List[set], set]:
    """
    细化聚类，确保每个节点只出现在一个聚类中
    
    Returns:
        Tuple[List[set], set]: (细化后的聚类列表, 已分配节点集合)
    """
    if max_size <= 0:
        return ensure_unique_clusters(communities, min_size=3)

    refined: List[set] = []
    stack: List[set] = [set(comm) for comm in communities]

    while stack:
        members = stack.pop()
        if len(members) <= max_size:
            refined.append(members)
            continue

        subgraph = graph.subgraph(members)
        if subgraph.number_of_edges() == 0:
            # 对于没有边的节点，不创建单节点聚类，而是跳过它们
            continue

        sub_communities = detect_clusters(subgraph, resolution, method)
        if len(sub_communities) == 1:
            refined.append(members)
            continue

        split_occurred = False
        for sub in sub_communities:
            if 0 < len(sub) < len(members):
                stack.append(sub)
                split_occurred = True

        if not split_occurred:
            refined.append(members)

    # 确保节点唯一性并过滤小聚类（最小3个节点）
    unique_clusters, assigned_nodes = ensure_unique_clusters(refined, min_size=3)
    
    LOGGER.info(
        "聚类细化完成: 原始聚类=%d, 细化后聚类=%d, 已分配节点=%d",
        len(communities), len(unique_clusters), len(assigned_nodes)
    )
    
    return unique_clusters, assigned_nodes


def build_output(
    nodes: List[Dict],
    links: List[Dict],
    graph: nx.Graph,
    metadata: Dict,
    max_cluster_size: int,
    resolution: float,
    cluster_method: str,
) -> Dict:
    metrics_lookup = metadata.pop("_metrics")  # type: ignore
    for node in nodes:
        node_id = node["id"]
        node["metrics"] = metrics_lookup.get(node_id, {})

    node_lookup = {node["id"]: node for node in nodes}
    all_node_ids = set(node["id"] for node in nodes)
    
    # 执行聚类
    communities = detect_clusters(graph, resolution, cluster_method)
    LOGGER.info("初始聚类检测: 发现 %d 个聚类", len(communities))
    
    # 细化聚类并确保唯一性
    communities, assigned_nodes = refine_clusters(communities, graph, max_cluster_size, resolution, cluster_method)
    
    # 检查未分配的节点
    unassigned_nodes = all_node_ids - assigned_nodes
    if unassigned_nodes:
        LOGGER.warning("发现 %d 个未分配到聚类的节点: %s", len(unassigned_nodes), list(unassigned_nodes)[:5])
        # 将未分配的节点标记为 cluster = -1
        for node_id in unassigned_nodes:
            if node_id in node_lookup:
                node_lookup[node_id]["cluster"] = -1
    
    # 验证节点唯一性
    clustered_nodes_check = set()
    for community in communities:
        overlap = clustered_nodes_check & community
        if overlap:
            LOGGER.error("聚类重叠检测失败! 发现重复节点: %s", overlap)
        clustered_nodes_check.update(community)
    
    # 构建聚类信息
    clusters_payload: List[Dict] = []
    for idx, members in enumerate(communities):
        color = DEFAULT_COLORS[idx % len(DEFAULT_COLORS)]
        clusters_payload.append(summarise_cluster(members, node_lookup, graph, color, idx))
        for node_id in members:
            node_lookup[node_id]["cluster"] = idx
    
    # 记录聚类统计
    LOGGER.info(
        "聚类完成: 总节点=%d, 聚类数=%d, 已分配=%d, 未分配=%d",
        len(all_node_ids), len(communities), len(assigned_nodes), len(unassigned_nodes)
    )
    
    # 添加聚类统计到元数据
    metadata["clusterStats"] = {
        "totalClusters": len(communities),
        "assignedNodes": len(assigned_nodes),
        "unassignedNodes": len(unassigned_nodes),
        "clusterSizes": [len(c) for c in communities],
    }

    return {
        "metadata": metadata,
        "nodes": nodes,
        "links": links,
        "clusters": clusters_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate events evolution network dataset (events.json)")
    parser.add_argument("--equipment-file", default="output/equipment_events.json", help="Path to external events JSON")
    parser.add_argument("--inner-file", default="output/inner_events.json", help="Path to internal events JSON")
    parser.add_argument("--output-file", default="output/events.json", help="Output file path")
    parser.add_argument("--similarity-threshold", type=float, default=0.72, help="语义相似度阈值，提高以减少不相关连接")
    parser.add_argument("--similarity-topk", type=int, default=3, help="每个节点的Top-K语义邻居数量，降低以减少连接密度")
    parser.add_argument("--attribute-weight", type=float, default=0.35, help="属性重叠边的基础权重，降低以减少属性连接影响")
    parser.add_argument("--cluster-method", choices=["leiden", "louvain", "greedy"], default="leiden", help="社区检测算法")
    parser.add_argument("--cluster-resolution", type=float, default=1.8, help="聚类分辨率参数，提高以产生更细粒度的聚类")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    embedding_url = os.environ.get("EMBEDDING_API_URL", DEFAULT_EMBEDDING_CONFIG["url"])
    model_name = os.environ.get("EMBEDDING_MODEL_NAME", DEFAULT_EMBEDDING_CONFIG["model"])
    api_type = os.environ.get("EMBEDDING_API_TYPE", DEFAULT_EMBEDDING_CONFIG["apiType"])
    timeout = int(os.environ.get("EMBEDDING_TIMEOUT", str(DEFAULT_EMBEDDING_CONFIG["timeout"])))
    dim = int(os.environ.get("EMBEDDING_DIM", str(DEFAULT_EMBEDDING_CONFIG["dimension"])))
    batch_size = int(os.environ.get("EMBEDDING_BATCH_SIZE", str(DEFAULT_EMBEDDING_CONFIG["batchSize"])))
    max_cluster_size = int(os.environ.get("MAX_CLUSTER_SIZE", "10"))
    resolution_env = os.environ.get("CLUSTER_RESOLUTION", os.environ.get("LOUVAIN_RESOLUTION"))
    resolution = float(resolution_env) if resolution_env is not None else args.cluster_resolution
    cluster_method = os.environ.get("CLUSTER_METHOD", args.cluster_method).lower()
    resolved_embedding_url = resolve_embedding_endpoint(embedding_url)
    LOGGER.info("Using embedding service base=%s, endpoint=%s", embedding_url, resolved_embedding_url)
    LOGGER.info("Clustering method=%s (resolution=%.3f)", cluster_method, resolution)

    external_events = load_events(args.equipment_file, "external")
    internal_events = load_events(args.inner_file, "internal")
    nodes = external_events + internal_events
    LOGGER.info("Loaded %d events (external %d / internal %d)", len(nodes), len(external_events), len(internal_events))

    prompts = [build_embedding_prompt(event) for event in nodes]
    embeddings, actual_dim = fetch_embeddings(
        prompts,
        resolved_embedding_url,
        model_name,
        timeout,
        batch_size,
        dim,
    )
    if actual_dim != dim:
        LOGGER.info("Adjusted embedding dimension: %d -> %d", dim, actual_dim)
    dim = actual_dim
    LOGGER.info("Embeddings generated, shape=%s", embeddings.shape)

    sim_matrix = cosine_similarity(embeddings)
    edge_map = build_semantic_edges(
        nodes,
        sim_matrix,
        threshold=args.similarity_threshold,
        top_k=args.similarity_topk,
    )
    build_attribute_edges(nodes, edge_map, args.attribute_weight)
    ensure_cross_source_links(nodes, sim_matrix, edge_map)
    apply_source_weighting(edge_map, {node["id"]: node for node in nodes})
    links = normalize_edges(edge_map)
    LOGGER.info("Generated %d weighted edges", len(links))
    graph, metrics = compute_network_metrics(nodes, links)
    metadata = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceFiles": {
            "external": os.path.abspath(args.equipment_file),
            "internal": os.path.abspath(args.inner_file),
        },
        "embedding": {
            "url": embedding_url,
            "resolvedUrl": resolved_embedding_url,
            "model": model_name,
            "apiType": api_type,
            "dimension": dim,
            "batchSize": batch_size,
        },
        "parameters": {
            "similarityThreshold": args.similarity_threshold,
            "similarityTopK": args.similarity_topk,
            "attributeWeight": args.attribute_weight,
            "maxClusterSize": max_cluster_size,
            "resolution": resolution,
            "clusterMethod": cluster_method,
        },
        "stats": {
            "nodeCount": len(nodes),
            "linkCount": len(links),
        },
        "_metrics": metrics,
    }

    payload = build_output(nodes, links, graph, metadata, max_cluster_size, resolution, cluster_method)
    with open(args.output_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    LOGGER.info("events.json written to %s", os.path.abspath(args.output_file))
if __name__ == "__main__":
    main()
