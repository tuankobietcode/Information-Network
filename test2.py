import networkx as nx
import math
import csv
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict

# 1. Hàm tính khoảng cách Haversine
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# 2. Đọc đồ thị và khởi tạo các giá trị
G = nx.read_gml(r'D:/InformationNetwork/AttMpls.gml', label='id')
for u, v, data in G.edges(data=True):
    n1, n2 = G.nodes[u], G.nodes[v]
    dist = haversine(n1['Latitude'], n1['Longitude'], n2['Latitude'], n2['Longitude'])
    data['distance'] = dist
    data['capacity'] = 100 if dist <= 1000 else 200 if dist <= 2000 else 300
    data['flow'] = 0.0

# 3. Đọc và sắp xếp Demands (Ưu tiên Small Bandwidth để đạt N_max)
demands = []
with open(r'D:/InformationNetwork/AttDemand.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        if row and not row[0].startswith('#'):
            demands.append((int(row[0]), int(row[1]), int(row[2]), float(row[3])))

demands.sort(key=lambda x: x[3]) # Small Bandwidth First

# 4. Routing và tính toán (Sử dụng trọng số động)
accepted = []
for seq, src, tgt, bw in demands:
    try:
        def dynamic_weight(u, v, d):
            if d['capacity'] - d['flow'] < bw: return float('inf')
            return d['distance'] * (1 + d['flow'] / d['capacity'])
        
        path = nx.shortest_path(G, src, tgt, weight=dynamic_weight)
        for i in range(len(path) - 1):
            G[path[i]][path[i+1]]['flow'] += bw
        accepted.append((seq, src, tgt, bw, path))
    except: continue

# 5. Phân tích Utilization
util_dist = {'0-30%': 0, '30-70%': 0, '70-100%': 0}
total_util = 0
for u, v, d in G.edges(data=True):
    u_rate = (d['flow'] / d['capacity']) * 100
    total_util += u_rate
    if u_rate <= 30: util_dist['0-30%'] += 1
    elif u_rate <= 70: util_dist['30-70%'] += 1
    else: util_dist['70-100%'] += 1

avg_util = total_util / G.number_of_edges()

# 6. Ghi kết quả ra ket_qua_toi_uu.txt
with open('ket_qua_toi_uu.txt', 'w', encoding='utf-8') as f:
    f.write("=== BÁO CÁO TỐI ƯU HÓA MẠNG AT&T ===\n\n")
    f.write(f"1. Tổng số demands chấp nhận (N_max): {len(accepted)}/{len(demands)}\n")
    f.write(f"2. Hiệu suất sử dụng Capacity trung bình: {avg_util:.2f}%\n\n")
    
    f.write("3. Phân bố Utilization các liên kết:\n")
    for k, v in util_dist.items():
        f.write(f"   - Nhóm {k}: {v} liên kết\n")
    
    f.write("\n4. Danh sách Demands và Tuyến đường (Paths):\n")
    f.write(f"{'Seq':<5} | {'Source':<7} | {'Target':<7} | {'BW':<7} | {'Path'}\n")
    f.write("-" * 80 + "\n")
    for seq, src, tgt, bw, path in accepted:
        path_str = " -> ".join(map(str, path))
        f.write(f"{seq:<5} | {src:<7} | {tgt:<7} | {bw:<7.1f} | {path_str}\n")

print("Đã xuất file kết quả: ket_qua_toi_uu.txt")

# 7. Vẽ đồ thị 
plt.figure(figsize=(12, 8))
pos = {n: (G.nodes[n]['Longitude'], G.nodes[n]['Latitude']) for n in G.nodes()}
edge_colors = ['red' if (d['flow']/d['capacity']) > 0.7 else 'orange' if (d['flow']/d['capacity']) > 0.3 else 'green' for u,v,d in G.edges(data=True)]

nx.draw(G, pos, node_size=400, node_color='skyblue', with_labels=True, edge_color=edge_colors, width=2, font_size=8)

# Chú thích 
legend_patches = [
    mpatches.Patch(color='red', label='Utilization > 70%'),
    mpatches.Patch(color='orange', label='30% - 70%'),
    mpatches.Patch(color='green', label='Utilization < 30%')
]
plt.legend(handles=legend_patches, loc='upper right', title="Trạng thái tải")
plt.title(f"Mạng AT&T - N_max = {len(accepted)}")
plt.show()