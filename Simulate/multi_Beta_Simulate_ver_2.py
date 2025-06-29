import os
import networkx as nx
import numpy as np
import pandas as pd
from tqdm import tqdm
from joblib import Parallel, delayed
from multiprocessing import cpu_count
import time

# ✅ THAM SỐ MÔ HÌNH
INF = 10000
EPSILON = 0.05
DELTA = 0.1
MAX_ITER = 50
TOL = 1e-4
N_BETA = 2  # ✅ Số lượng Beta mỗi nhóm

# ✅ B1: Đọc mạng từ file
def import_network(file_path):
    with open(file_path, "r") as f:
        data = f.readlines()[1:]
    G = nx.DiGraph()
    for line in data:
        from_node, to_node, direction, weight = line.strip().split("\t")
        direction = int(direction)
        weight = float(weight)
        G.add_edge(from_node, to_node, weight=float(weight))
        if direction == 0:
            G.add_edge(to_node, from_node, weight=float(weight))
    return G

# ✅ B2: Tạo ma trận kề
def build_adjacency(G, node_order):
    n = len(node_order)
    node_index = {node: i for i, node in enumerate(node_order)}
    A = np.zeros((n, n))
    neighbors = {i: [] for i in range(n)}
    for u, v, data in G.edges(data=True):
        i, j = node_index[u], node_index[v]
        A[i, j] += data.get("weight", 1.0)
        neighbors[j].append(i)
    return A, neighbors, node_index

# ✅ B3: Cập nhật trạng thái
def update_states_multi_beta(x, A, neighbors, beta_indices, beta_weights, fixed_nodes):
    n = len(x)
    x_new = x.copy()
    for u in range(n):
        if u in fixed_nodes:
            continue
        influence = EPSILON * sum(A[v, u] * (x[v] - x[u]) for v in neighbors[u])
        beta_influence = DELTA * sum(
            w * (x[b] - x[u]) for b, w in zip(beta_indices, beta_weights[u])
        )
        x_new[u] = x[u] + influence + beta_influence
    return np.clip(x_new, -1000, 1000)

# ✅ B4: Gắn Beta vào đúng 1 node target, cập nhật x
def simulate_beta_on_target(G, beta_nodes, target_node, x_prev=None, alpha_idx=None, node_order=None):
    """
    Mô phỏng cạnh tranh ngoài với nhóm Beta gắn vào đúng 1 node (target_node).
    Nếu x_prev không được cung cấp, tự khởi tạo và gán trạng thái cho Alpha.
    """
    if node_order is None:
        node_order = list(G.nodes())

    all_nodes = node_order + [f"Beta{i}" for i in range(len(beta_nodes))]
    A, neighbors, node_index = build_adjacency(G, all_nodes)
    n = len(all_nodes)

    # ✅ Tự khởi tạo trạng thái nếu x_prev chưa có
    if x_prev is None:
        x_prev = np.zeros(n)
        if alpha_idx is not None:
            alpha_node_name = node_order[alpha_idx]
            alpha_idx_in_new = node_index[alpha_node_name]
            x_prev[alpha_idx_in_new] = 1

    # ✅ Căn chỉnh độ dài x_prev nếu cần
    if x_prev.shape[0] != n:
        x_prev = np.pad(x_prev, (0, n - x_prev.shape[0]), mode="constant")

    x = x_prev.copy()
    beta_indices = []
    fixed_nodes = set()
    beta_weights = [[0] * len(beta_nodes) for _ in range(n)]

    # ✅ Gán tất cả Beta vào cùng 1 node (target_node)
    for i, beta in enumerate(beta_nodes):
        beta_name = f"Beta{i}"
        beta_idx = node_index[beta_name]
        A[beta_idx, node_index[target_node]] = 1.0
        neighbors[node_index[target_node]].append(beta_idx)
        x[beta_idx] = -1
        beta_indices.append(beta_idx)
        fixed_nodes.add(beta_idx)
        beta_weights[node_index[target_node]][i] = 1.0

    # ✅ Cập nhật trạng thái
    for _ in range(MAX_ITER):
        x_new = update_states_multi_beta(x, A, neighbors, beta_indices, beta_weights, fixed_nodes)
        if np.linalg.norm(x_new - x) < TOL:
            break
        x = x_new

    return x[:len(G.nodes())]  # Trả về trạng thái của node thường (không gồm Beta)


# ✅ B5: Tổng hỗ trợ
def compute_total_support(x_state, alpha_idx):
    return sum(1 if x > 0 else -1 if x < 0 else 0 for i, x in enumerate(x_state) if i != alpha_idx)

# ✅ B6: Xử lý 1 node Alpha
def process_alpha(alpha_node, G, beta_nodes):
    node_order = list(G.nodes())
    alpha_idx = node_order.index(alpha_node)
    x_state = np.zeros(len(node_order))
    x_state[alpha_idx] = 1
    support = 0

    for target_node in node_order:
        if target_node == alpha_node:
            continue
        x_state = simulate_beta_on_target(G, beta_nodes, target_node, x_state, alpha_idx, node_order)

    support = compute_total_support(x_state, alpha_idx)
    return {"Alpha_Node": alpha_node, "Total_Support": support}

# ✅ B7: MAIN
def main():
    input_folder = "data_1"
    # ✅ Tạo tên thư mục dựa trên giá trị tham số
    output_folder = f"Output_test/INF{INF}_EPS{EPSILON}_DELTA{DELTA}_ITER{MAX_ITER}_TOL{TOL}_NBETA{N_BETA}"
    os.makedirs(output_folder, exist_ok=True)


    for file in os.listdir(input_folder):
        if not file.endswith(".txt"):
            continue
        path = os.path.join(input_folder, file)
        G = import_network(path)
        all_nodes = list(G.nodes())

        results = Parallel(n_jobs = -1)(
            delayed(process_alpha)(alpha_node, G, all_nodes[:N_BETA])
            for alpha_node in tqdm(all_nodes, desc=f"🔁 Xử lý file {file}")
        )

        df = pd.DataFrame(results)
        df.to_csv(os.path.join(output_folder, file.replace(".txt", ".csv")), index=False)
        print(f"✅ Xong: {file}")

if __name__ == "__main__":
    main()
