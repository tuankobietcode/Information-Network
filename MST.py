import networkx as nx
import math
import matplotlib.pyplot as plt

# 1. Hàm tính khoảng cách Haversine
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# 2. Đọc file GML
G = nx.read_gml(r'D:/InformationNetwork/AttMpls.gml', label='id')

# 3. Tính khoảng cách và gán capacity cho từng cạnh
for u, v, data in G.edges(data=True):
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    lat1, lon1 = node_u['Latitude'], node_u['Longitude']
    lat2, lon2 = node_v['Latitude'], node_v['Longitude']
    
    distance = haversine(lat1, lon1, lat2, lon2)
    data['distance'] = distance
    
    if distance <= 1000:
        capacity = 100
    elif 1000 < distance <= 2000:
        capacity = 200
    elif 2000 < distance <= 3000:
        capacity = 300
    else:
        capacity = 300
    
    data['capacity'] = capacity
    data['flow'] = 0.0
    data['residual'] = capacity
    data['demandsID'] = []

# 4. Thuật toán Prim để tìm MST
def prim_mst(graph):
    # Khởi tạo
    visited = set()
    mst_edges = []
    total_distance = 0
    
    # Bắt đầu từ node 0
    start_node = 0
    visited.add(start_node)
    
    # Tạo danh sách các cạnh từ node đã thăm đến node chưa thăm
    while len(visited) < graph.number_of_nodes():
        min_edge = None
        min_distance = float('inf')
        
        for u in visited:
            for v in graph.neighbors(u):
                if v not in visited:
                    # Tìm cạnh (u, v) trong đồ thị
                    if graph.has_edge(u, v):
                        distance = graph[u][v]['distance']
                        if distance < min_distance:
                            min_distance = distance
                            min_edge = (u, v)
        
        # Thêm cạnh nhỏ nhất vào MST
        if min_edge:
            u, v = min_edge
            visited.add(v)
            mst_edges.append((u, v))
            total_distance += min_distance
    
    # Tạo đồ thị MST từ các cạnh
    mst = nx.Graph()
    for node in graph.nodes():
        mst.add_node(node, **graph.nodes[node])
    
    for u, v in mst_edges:
        mst.add_edge(u, v, **graph[u][v])
    
    return mst, total_distance

# 5. Tìm MST và tổng khoảng cách
mst, total_mst_distance = prim_mst(G)


print("THÔNG TIN MST (PRIM ALGORITHM)")
print(f"Số nút trong MST: {mst.number_of_nodes()}")
print(f"Số cạnh trong MST: {mst.number_of_edges()}")
print(f"Tổng khoảng cách MST: {total_mst_distance:.2f} km")
print("\nDanh sách các cạnh trong MST:")
for u, v, data in mst.edges(data=True):
    print(f"({u}, {v}): distance = {data['distance']:.2f} km, capacity = {data['capacity']} Mbps")

# 6. Vẽ đồ thị so sánh: Gốc vs MST
pos = {node: (G.nodes[node]['Longitude'], G.nodes[node]['Latitude']) for node in G.nodes()}

plt.figure(figsize=(16, 6))

# Subplot 1: Đồ thị gốc
plt.subplot(1,3,1)
nx.draw(G, pos, with_labels=True, node_color='lightblue', 
        node_size=500, font_size=8, font_weight='bold')
plt.title("AT&T Backbone Network (Original)\nAll edges")

# Subplot 2: MST
plt.subplot(1,3,2)
nx.draw(mst, pos, with_labels=True, node_color='lightgreen', 
        node_size=500, font_size=8, font_weight='bold', edge_color='red')
plt.title(f"MST (Prim Algorithm)\nTotal distance: {total_mst_distance:.2f} km")

plt.tight_layout()


# 7. Vẽ đồ thị kết hợp(nét liền và nét đứt)
plt.subplot(1,3,3)

# Vẽ tất cả các nút
nx.draw_networkx_nodes(G, pos, node_color='lightblue', node_size=500)

# Vẽ các cạnh không thuộc MST (nét đứt)
non_mst_edges = [(u, v) for (u, v) in G.edges() if not mst.has_edge(u, v)]
nx.draw_networkx_edges(G, pos, edgelist=non_mst_edges, 
                       edge_color='gray', style='dashed', width=1)

# Vẽ các cạnh thuộc MST (nét liền, màu đậm)
mst_edges = list(mst.edges())
nx.draw_networkx_edges(G, pos, edgelist=mst_edges, 
                       edge_color='red', style='solid', width=2)

# Vẽ nhãn nút
nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')

plt.title(f"AT&T Network with MST (Prim)\nSolid: MST edges,\n Dashed: Non-MST edges\nTotal MST distance: {total_mst_distance:.2f} km")
plt.axis('off')
plt.tight_layout()
plt.show()

# 8. Lưu MST ra file để dùng cho bước sau
nx.write_gml(mst, "AttMpls_MST.gml")