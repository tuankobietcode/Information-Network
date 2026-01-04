import networkx as nx
import math
import csv

# 1. Hàm tính khoảng cách Haversine
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# 2. Đọc đồ thị và thiết lập capacity theo khoảng cách
print("Đang đọc đồ thị từ AttMpls.gml...")
G = nx.read_gml(r'D:/InformationNetwork/AttMpls.gml', label='id')

for u, v, data in G.edges(data=True):
    node_u = G.nodes[u]
    node_v = G.nodes[v]
    lat1, lon1 = node_u['Latitude'], node_u['Longitude']
    lat2, lon2 = node_v['Latitude'], node_v['Longitude']
    
    distance = haversine(lat1, lon1, lat2, lon2)
    data['distance'] = distance
    
    # Capacity theo khoảng cách (ĐÚNG ĐỀ BÀI)
    if distance <= 1000:
        capacity = 100
    elif distance <= 2000:
        capacity = 200
    else:
        capacity = 300
    
    data['capacity'] = capacity
    data['flow'] = 0.0
    data['residual'] = capacity
    data['demandsID'] = []

# 3. Đọc demands từ file CSV (giữ NGUYÊN thứ tự)
print("Đang đọc demands từ AttDemand.csv...")
demands = []
with open('D:/InformationNetwork/AttDemand.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)  # Bỏ header
    
    for row in reader:
        if not row or row[0].startswith('#'):
            continue
        
        seq = int(row[0])
        source = int(row[1])
        target = int(row[2])
        bandwidth = float(row[3])
        demands.append((seq, source, target, bandwidth))

print(f"Đã đọc {len(demands)} demands từ file")
print(f"Tổng bandwidth demand: {sum(bw for _, _, _, bw in demands):.1f} Mbps")

# 4. Hàm FCFS - xử lý theo thứ tự từ trên xuống dưới
def fcfs_process_demands(demands_list, graph):
    """Xử lý demands theo FCFS (First-Come-First-Served)"""
    print("\n" + "="*60)
    print("PHƯƠNG PHÁP: FCFS (First-Come-First-Served)")
    print("="*60)
    
    # Reset đồ thị
    for u, v, data in graph.edges(data=True):
        data['flow'] = 0.0
        data['residual'] = data['capacity']
        data['demandsID'] = []
    
    accepted = []
    rejected = []
    
    # Xử lý demands theo đúng thứ tự từ file
    for seq, source, target, bandwidth in demands_list:
        # Kiểm tra nếu source và target tồn tại trong đồ thị
        if source not in graph.nodes() or target not in graph.nodes():
            rejected.append((seq, source, target, bandwidth, "Node không tồn tại"))
            continue
        
        # Tìm đường đi ngắn nhất có đủ bandwidth
        try:
            # Tạo đồ thị tạm chỉ chứa các cạnh có đủ residual
            temp_graph = graph.copy()
            edges_to_remove = []
            for u, v, data in temp_graph.edges(data=True):
                if data['residual'] < bandwidth:
                    edges_to_remove.append((u, v))
            
            # Xóa các cạnh không đủ bandwidth
            temp_graph.remove_edges_from(edges_to_remove)
            
            # Tìm đường đi ngắn nhất
            path = nx.shortest_path(temp_graph, source, target, weight='distance')
            
            # Nếu tìm được đường, cập nhật flow
            for i in range(len(path) - 1):
                u, v = path[i], path[i + 1]
                if not graph.has_edge(u, v):
                    u, v = v, u
                
                graph[u][v]['residual'] -= bandwidth
                graph[u][v]['flow'] += bandwidth
                graph[u][v]['demandsID'].append(seq)
            
            accepted.append((seq, source, target, bandwidth, path))
            
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            rejected.append((seq, source, target, bandwidth, "Không tìm thấy đường đi đủ bandwidth"))
    
    # Tính toán kết quả
    total_demand_bw = sum(bw for _, _, _, bw in demands_list)
    total_accepted_bw = sum(bw for _, _, _, bw, _ in accepted)
    
    # Đếm link > 70% utilization
    high_util_links = []
    for u, v, data in graph.edges(data=True):
        if data['capacity'] > 0:
            util = data['flow'] / data['capacity']
            if util > 0.7:
                high_util_links.append((u, v, util))
    
    print(f"Số demands được chấp nhận (N): {len(accepted)}/{len(demands_list)}")
    print(f"Tỷ lệ chấp nhận: {len(accepted)/len(demands_list)*100:.1f}%")
    print(f"Bandwidth được chấp nhận: {total_accepted_bw:.1f}/{total_demand_bw:.1f} Mbps")
    print(f"Tỷ lệ bandwidth: {total_accepted_bw/total_demand_bw*100:.1f}%")
    print(f"Liên kết >70% capacity: {len(high_util_links)}")
    
    return accepted, rejected, high_util_links, total_accepted_bw

# 5. Chạy FCFS với demands nguyên bản
accepted, rejected, high_util, total_bw = fcfs_process_demands(demands, G)

# 6. Hiển thị kết quả chi tiết
print("\n" + "="*60)
print("KẾT QUẢ CHI TIẾT FCFS")
print("="*60)

# Hiển thị 10 demands đầu tiên được chấp nhận
if accepted:
    print("\n DEMANDS ĐẦU TIÊN ĐƯỢC CHẤP NHẬN:")
    print("-")
    print(f"{'Seq':<5} {'Source':<8} {'Target':<8} {'Bandwidth':<12} {'Path Length'}")
    print("-"*60)
    for seq, source, target, bandwidth, path in accepted[:]:
        print(f"{seq:<5} {source:<8} {target:<8} {bandwidth:<12.1f} {len(path)-1}")

# Hiển thị 10 demands đầu tiên bị từ chối
if rejected and len(rejected) > 0:
    print(f"\n DEMANDS ĐẦU TIÊN BỊ TỪ CHỐI (tổng: {len(rejected)}):")
    print("-"*60)
    print(f"{'Seq':<5} {'Source':<8} {'Target':<8} {'Bandwidth':<12} {'Lý do'}")
    print("-"*60)
    for seq, source, target, bandwidth, reason in rejected[:10]:
        print(f"{seq:<5} {source:<8} {target:<8} {bandwidth:<12.1f} {reason}")

# 7. Phân tích utilization
print("\n" + "="*60)
print("PHÂN TÍCH UTILIZATION MẠNG")
print("="*60)

# Tính average utilization
total_util = 0
count = 0
util_dist = {'0-30%': 0, '30-70%': 0, '70-100%': 0}

for u, v, data in G.edges(data=True):
    if data['capacity'] > 0:
        util = data['flow'] / data['capacity']
        total_util += util
        count += 1
        
        util_pct = util * 100
        if util_pct <= 30:
            util_dist['0-30%'] += 1
        elif util_pct <= 70:
            util_dist['30-70%'] += 1
        else:
            util_dist['70-100%'] += 1

avg_util = (total_util / count * 100) if count > 0 else 0
print(f"Average link utilization: {avg_util:.1f}%")

# Tổng capacity mạng
total_capacity = sum(data['capacity'] for _, _, data in G.edges(data=True))
print(f"Tổng network capacity: {total_capacity:.0f} Mbps")
print(f"Hiệu suất sử dụng capacity: {total_bw/total_capacity*100:.1f}%")

print("\nPhân bố utilization:")
for range_name, cnt in util_dist.items():
    perc = cnt / G.number_of_edges() * 100
    print(f"  {range_name}: {cnt} links ({perc:.1f}%)")

# 8. Lưu kết quả vào file
with open('FCFS_result.txt', 'w', encoding='utf-8') as f:
    f.write("KẾT QUẢ FCFS (First-Come-First-Served)\n")
    f.write("="*50 + "\n")
    f.write(f"Số demands được chấp nhận (N): {len(accepted)}/{len(demands)}\n")
    f.write(f"Tỷ lệ chấp nhận: {len(accepted)/len(demands)*100:.1f}%\n")
    f.write(f"Bandwidth accepted: {total_bw:.1f} Mbps\n")
    f.write(f"Average utilization: {avg_util:.1f}%\n")
    f.write(f"Links >70%: {len(high_util)}\n\n")
    
    f.write("DEMANDS ĐƯỢC CHẤP NHẬN:\n")
    f.write("-"*50 + "\n")
    for seq, source, target, bandwidth, path in accepted[:]:  # Lưu 50 đầu
        f.write(f"Seq {seq}: {source}→{target}, BW={bandwidth} Mbps, Hops={len(path)-1}\n")
    
    

print("\n" + "="*60)
print("KẾT LUẬN FCFS:")
print("="*60)
print(f"Với phương pháp FCFS (xử lý theo thứ tự từ trên xuống dưới):")
print(f"• Số demands có thể được chấp nhận: N = {len(accepted)} demands")
print(f"• Tỷ lệ thành công: {len(accepted)/len(demands)*100:.1f}%")
print(f"• Kết quả đã lưu vào: FCFS_result.txt")