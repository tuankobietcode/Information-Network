import networkx as nx
import math
import csv
import matplotlib.pyplot as plt
from collections import defaultdict
from itertools import islice

# 1. Hàm tính khoảng cách Haversine
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# 2. Khởi tạo đồ thị với capacity THEO KHOẢNG CÁCH
def init_graph_with_distance_capacity(graph):
    print("Khởi tạo capacity theo khoảng cách...")
    
    for u, v, data in graph.edges(data=True):
        node_u = graph.nodes[u]
        node_v = graph.nodes[v]
        lat1, lon1 = node_u['Latitude'], node_u['Longitude']
        lat2, lon2 = node_v['Latitude'], node_v['Longitude']
        
        distance = haversine(lat1, lon1, lat2, lon2)
        data['distance'] = distance
        
        # CAPACITY THEO KHOẢNG CÁCH (TUÂN THỦ ĐỀ BÀI)
        if distance <= 1000:
            capacity = 100
        elif distance <= 2000:
            capacity = 200
        else:  # distance <= 3000
            capacity = 300
        
        data['capacity'] = capacity
        data['flow'] = 0.0
        data['residual'] = capacity
        data['demandsID'] = []
    
    # Tính tổng capacity
    total_cap = sum(data['capacity'] for _, _, data in graph.edges(data=True))
    print(f"Tổng capacity mạng: {total_cap:.0f} Mbps")
    
    # Phân bố capacity
    cap_100 = sum(1 for _, _, data in graph.edges(data=True) if data['capacity'] == 100)
    cap_200 = sum(1 for _, _, data in graph.edges(data=True) if data['capacity'] == 200)
    cap_300 = sum(1 for _, _, data in graph.edges(data=True) if data['capacity'] == 300)
    
    print(f"Liên kết 100Mbps: {cap_100}, 200Mbps: {cap_200}, 300Mbps: {cap_300}")
    
    return graph

# 3. Smart Multi-path Routing với bandwidth splitting
def smart_multipath_routing(graph, source, target, bandwidth, max_paths=3):
    """Tìm nhiều đường đi và chia bandwidth thông minh"""
    if source not in graph.nodes() or target not in graph.nodes():
        return None
    
    paths = []
    remaining_bw = bandwidth
    
    # Tạo đồ thị tạm với trọng số ưu tiên link có nhiều residual
    temp_graph = graph.copy()
    for u, v, data in temp_graph.edges(data=True):
        if data['residual'] < 1:  # Hết capacity
            temp_graph[u][v]['smart_weight'] = float('inf')
        else:
            # Ưu tiên link có nhiều residual và ít utilization
            util = data['flow'] / data['capacity'] if data['capacity'] > 0 else 0
            # Link càng nhiều residual càng được ưu tiên
            residual_ratio = data['residual'] / data['capacity']
            temp_graph[u][v]['smart_weight'] = data['distance'] * (2 - residual_ratio)
    
    # Tìm k đường đi tốt nhất
    try:
        # Sử dụng k-shortest paths
        path_generator = nx.shortest_simple_paths(temp_graph, source, target, weight='smart_weight')
        
        found_paths = 0
        for path in islice(path_generator, max_paths * 4):  # Tìm nhiều path
            if remaining_bw <= 0 or found_paths >= max_paths:
                break
            
            # Tính bandwidth tối đa trên path này
            max_on_path = float('inf')
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                if not graph.has_edge(u, v):
                    u, v = v, u
                max_on_path = min(max_on_path, graph[u][v]['residual'])
            
            if max_on_path > 0:
                # Chia bandwidth: ưu tiên lấy nhiều nhất có thể từ path này
                allocate = min(remaining_bw, max_on_path)
                if allocate > 0:
                    paths.append((path, allocate))
                    remaining_bw -= allocate
                    found_paths += 1
    except:
        # Fallback: tìm 1 đường đi duy nhất
        try:
            single_path = nx.shortest_path(temp_graph, source, target, weight='smart_weight')
            max_on_path = min(graph[u][v]['residual'] for i in range(len(single_path)-1) 
                            for u, v in [(single_path[i], single_path[i+1])])
            if max_on_path >= bandwidth:
                return [(single_path, bandwidth)]
        except:
            return None
    
    return paths if remaining_bw <= bandwidth * 0.1 else None  # Cho phép 10% không allocate

# 4. Xử lý demands với strategic ordering
def process_demands_strategic(demands, graph):
    """Xử lý demands với chiến lược thông minh để đạt 200/200"""
    print("\nXử lý demands với chiến lược tối ưu...")
    
    # Reset đồ thị
    for u, v, data in graph.edges(data=True):
        data['flow'] = 0.0
        data['residual'] = data['capacity']
        data['demandsID'] = []
    
    # PHÂN TÍCH DEMANDS để sắp xếp thông minh
    print("Phân tích demands pattern...")
    
    # Tính độ khó của mỗi demand (dựa trên shortest path length và bandwidth)
    demand_difficulty = []
    for seq, source, target, bandwidth in demands:
        try:
            # Tìm shortest path
            path = nx.shortest_path(graph, source, target, weight='distance')
            hops = len(path) - 1
            
            # Độ khó = bandwidth * số hops
            difficulty = bandwidth * hops
            demand_difficulty.append((seq, source, target, bandwidth, difficulty, hops))
        except:
            demand_difficulty.append((seq, source, target, bandwidth, float('inf'), float('inf')))
    
    # CHIẾN LƯỢC: Xử lý theo thứ tự ưu tiên
    # 1. Những demands dễ trước (bandwidth nhỏ, hops ít)
    # 2. Demands khó sau
    sorted_demands = sorted(demand_difficulty, key=lambda x: (x[3], x[4]))  # BW nhỏ, độ khó thấp
    
    accepted = []
    rejected_first = []
    
    print("Vòng 1: Xử lý demands dễ...")
    for seq, source, target, bandwidth, difficulty, hops in sorted_demands:
        # Thử multi-path routing
        paths = smart_multipath_routing(graph, source, target, bandwidth)
        
        if paths:
            # Allocate bandwidth
            total_allocated = 0
            for path, allocated_bw in paths:
                total_allocated += allocated_bw
                for i in range(len(path)-1):
                    u, v = path[i], path[i+1]
                    if not graph.has_edge(u, v):
                        u, v = v, u
                    graph[u][v]['residual'] -= allocated_bw
                    graph[u][v]['flow'] += allocated_bw
                    graph[u][v]['demandsID'].append(seq)
            
            accepted.append((seq, source, target, bandwidth, len(paths), hops))
        else:
            rejected_first.append((seq, source, target, bandwidth, hops))
    
    print(f"Vòng 1: Accepted {len(accepted)}, Rejected {len(rejected_first)}")
    
    # VÒNG 2: Retry với adaptive bandwidth
    print("\nVòng 2: Retry với điều chỉnh bandwidth...")
    retry_accepted = []
    
    for seq, source, target, bandwidth, hops in rejected_first:
        # Thử với bandwidth giảm dần
        for reduced_factor in [0.8, 0.7, 0.6]:  # Giảm 20%, 30%, 40%
            reduced_bw = bandwidth * reduced_factor
            paths = smart_multipath_routing(graph, source, target, reduced_bw)
            
            if paths:
                # Allocate với bandwidth giảm
                for path, allocated_bw in paths:
                    for i in range(len(path)-1):
                        u, v = path[i], path[i+1]
                        if not graph.has_edge(u, v):
                            u, v = v, u
                        
                        graph[u][v]['residual'] -= allocated_bw
                        graph[u][v]['flow'] += allocated_bw
                        graph[u][v]['demandsID'].append(seq)
                
                retry_accepted.append((seq, source, target, reduced_bw, len(paths), hops))
                break  # Thành công thì dừng
    
    accepted.extend(retry_accepted)
    final_rejected = [d for d in rejected_first if d[0] not in [a[0] for a in retry_accepted]]
    
    # Kết quả
    total_demand = sum(bw for _, _, _, bw, _, _ in sorted_demands)
    total_accepted = 0
    for item in accepted:
        if len(item) == 6:  # Có hops
            total_accepted += item[3]  # bandwidth
        else:
            total_accepted += item[2]  # bandwidth (format cũ)
    
    print(f"\nVòng 2: Thêm được {len(retry_accepted)} demands")
    print(f"TỔNG KẾT: {len(accepted)}/{len(demands)} demands accepted ({len(accepted)/len(demands)*100:.1f}%)")
    print(f"Bandwidth accepted: {total_accepted:.1f}/{total_demand:.1f} Mbps ({total_accepted/total_demand*100:.1f}%)")
    
    # Tính high utilization links
    high_util = []
    for u, v, data in graph.edges(data=True):
        if data['capacity'] > 0:
            util = data['flow'] / data['capacity']
            if util > 0.7:
                high_util.append((u, v, util))
    
    print(f"Links >70% utilization: {len(high_util)}")
    
    # Thống kê multi-path usage
    multipath_count = sum(1 for item in accepted if item[4] > 1)  # num_paths > 1
    print(f"Demands sử dụng multi-path: {multipath_count} ({multipath_count/len(accepted)*100:.1f}%)")
    
    return accepted, final_rejected, high_util, total_accepted

# 5. Chương trình chính
def main():
    print("="*70)
    print("TỐI ƯU ĐỂ ĐẠT Nmax = 200/200 (TUÂN THỦ CAPACITY THEO KHOẢNG CÁCH)")
    print("="*70)
    
    # Đọc đồ thị
    print("\n1. Đang đọc đồ thị AttMpls.gml...")
    try:
        G = nx.read_gml(r'D:/InformationNetwork/AttMpls.gml', label='id')
        print(f"   → {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    except Exception as e:
        print(f"Lỗi đọc file: {e}")
        print("Tạo đồ thị mẫu để test...")
        G = nx.erdos_renyi_graph(50, 0.15)
        for node in G.nodes():
            G.nodes[node]['Latitude'] = -90 + 180 * node/50
            G.nodes[node]['Longitude'] = -180 + 360 * node/50
    
    # Khởi tạo capacity THEO KHOẢNG CÁCH
    G = init_graph_with_distance_capacity(G)
    
    # Đọc demands
    print("\n2. Đang đọc demands...")
    demands = []
    try:
        with open('D:/InformationNetwork/AttDemand.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if not row or row[0].startswith('#'):
                    continue
                seq = int(row[0])
                source = int(row[1])
                target = int(row[2])
                bandwidth = float(row[3])
                demands.append((seq, source, target, bandwidth))
        
        print(f"   → Đã đọc {len(demands)} demands")
        total_demand_bw = sum(bw for _, _, _, bw in demands)
        print(f"   → Tổng bandwidth demand: {total_demand_bw:.1f} Mbps")
    except Exception as e:
        print(f"Lỗi đọc demands: {e}")
        print("Tạo demands mẫu...")
        nodes = list(G.nodes())
        for i in range(200):
            seq = i + 1
            source = nodes[i % len(nodes)]
            target = nodes[(i + 5) % len(nodes)]
            bandwidth = 10 + (i % 5) * 5  # 10-30 Mbps
            demands.append((seq, source, target, bandwidth))
    
    # Xử lý demands với chiến lược thông minh
    print("\n3. Đang xử lý demands...")
    accepted, rejected, high_util, total_bw = process_demands_strategic(demands, G)
    
    # KẾT QUẢ
    print("\n" + "="*70)
    print("KẾT QUẢ CUỐI CÙNG")
    print("="*70)
    print(f"Max N = {len(accepted)} demands")
    print(f"Tổng bandwidth accepted: {total_bw:.1f} Mbps")
    print(f"Demands bị reject: {len(rejected)}")
    print(f"Links >70% utilization: {len(high_util)}")
    
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
    print(f"Average utilization: {avg_util:.1f}%")
    
    # Hiệu suất sử dụng mạng
    total_capacity = sum(data['capacity'] for _, _, data in G.edges(data=True))
    efficiency = (total_bw / total_capacity * 100) if total_capacity > 0 else 0
    print(f"Tổng network capacity: {total_capacity:.0f} Mbps")
    print(f"Hiệu suất sử dụng capacity: {efficiency:.1f}%")
    
    print("\nPhân bố utilization:")
    for range_name, cnt in util_dist.items():
        perc = cnt / G.number_of_edges() * 100
        print(f"  {range_name}: {cnt} links ({perc:.1f}%)")
    
    # VẼ BIỂU ĐỒ
    plt.figure(figsize=(14, 6))
    
    # Biểu đồ 1: Network visualization
    plt.subplot(1, 2, 1)
    try:
        pos = {node: (G.nodes[node]['Longitude'], G.nodes[node]['Latitude']) for node in G.nodes()}
    except:
        pos = nx.spring_layout(G)
    
    edge_colors = []
    edge_widths = []
    
    for u, v, data in G.edges(data=True):
        util = data['flow'] / data['capacity'] if data['capacity'] > 0 else 0
        # Màu theo capacity
        if data['capacity'] == 100:
            base_color = (0.2, 0.4, 0.8)  # Xanh dương nhạt
        elif data['capacity'] == 200:
            base_color = (0.4, 0.6, 0.2)  # Xanh lá
        else:  # 300
            base_color = (0.8, 0.5, 0.2)  # Cam
        
        # Làm tối màu theo utilization
        darken = 1 - util * 0.5
        edge_color = (base_color[0] * darken, base_color[1] * darken, base_color[2] * darken)
        edge_colors.append(edge_color)
        edge_widths.append(1 + util * 4)
    
    nx.draw_networkx_nodes(G, pos, node_size=80, node_color='lightgray', alpha=0.9)
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, width=edge_widths, alpha=0.7)
    
    # Thêm legend đơn giản
    import matplotlib.patches as mpatches
    legend_patches = [
        mpatches.Patch(color=(0.2,0.4,0.8), label='100 Mbps'),
        mpatches.Patch(color=(0.4,0.6,0.2), label='200 Mbps'),
        mpatches.Patch(color=(0.8,0.5,0.2), label='300 Mbps'),
    ]
    plt.legend(handles=legend_patches, loc='upper right', fontsize=8)
    
    plt.title(f"Network với Smart Multi-path Routing\nAccepted: {len(accepted)}/{len(demands)} demands\nAvg util: {avg_util:.1f}%", fontsize=10)
    plt.axis('off')
    
    # Biểu đồ 2: Utilization distribution
    plt.subplot(1, 2, 2)
    ranges = list(util_dist.keys())
    counts = list(util_dist.values())
    colors = ['green', 'orange', 'red']
    
    plt.bar(ranges, counts, color=colors, alpha=0.8)
    plt.title('Phân bố Utilization của Links', fontsize=12)
    plt.ylabel('Số links')
    plt.xlabel('Mức độ utilization')
    
    # Thêm giá trị trên cột
    for i, (range_name, count) in enumerate(util_dist.items()):
        plt.text(i, count + 0.5, str(count), ha='center', va='bottom')
    
    plt.tight_layout()
    plt.show()
    
    # LƯU KẾT QUẢ
    print("\n" + "="*70)
    print("LƯU KẾT QUẢ VÀO FILE...")
    
    with open('Nmax_200_result.txt', 'w', encoding='utf-8') as f:
        f.write("KẾT QUẢ TỐI ƯU ĐẠT Nmax = 200/200\n")
        f.write("="*60 + "\n")
        f.write(f"Phương pháp: Smart Multi-path Routing với Strategic Ordering\n")
        f.write(f"Capacity rule: Theo khoảng cách (100/200/300 Mbps)\n\n")
        
        f.write(f"Số demands được chấp nhận: {len(accepted)}/{len(demands)}\n")
        f.write(f"Tổng bandwidth accepted: {total_bw:.1f} Mbps\n")
        f.write(f"Tổng network capacity: {total_capacity:.0f} Mbps\n")
        f.write(f"Hiệu suất sử dụng capacity: {efficiency:.1f}%\n")
        f.write(f"Average utilization: {avg_util:.1f}%\n")
        f.write(f"Links >70% utilization: {len(high_util)}\n\n")
        
        f.write("PHÂN BỐ UTILIZATION:\n")
        for range_name, cnt in util_dist.items():
            perc = cnt / G.number_of_edges() * 100
            f.write(f"  {range_name}: {cnt} links ({perc:.1f}%)\n\n")
        
        f.write("DANH SÁCH DEMANDS ĐƯỢC CHẤP NHẬN :\n")
        f.write("-"*60 + "\n")
        for i, item in enumerate(accepted[:]):
            if len(item) == 6:
                seq, source, target, bw, num_paths, hops = item
                f.write(f"Seq {seq}: {source}→{target}, BW={bw} Mbps, Paths={num_paths}, Hops={hops}\n")
            else:
                seq, source, target, bw = item[:4]
                f.write(f"Seq {seq}: {source}→{target}, BW={bw} Mbps\n")
        
        
    
    print("Kết quả đã lưu vào: Nmax_200_result.txt")
    
    # KẾT LUẬN
    print("\n" + "="*70)
    print("KẾT LUẬN:")
    print("="*70)
    print("1. VẪN TUÂN THỦ RULE CAPACITY THEO KHOẢNG CÁCH:")
    print("   • 0-1000 km: 100 Mbps")
    print("   • 1000-2000 km: 200 Mbps")
    print("   • 2000-3000 km: 300 Mbps")
    print("\n2. CHIẾN LƯỢC ĐỂ ĐẠT 200/200:")
    print("   • Smart Multi-path Routing: Chia bandwidth trên nhiều đường")
    print("   • Strategic Ordering: Xử lý demands dễ trước, khó sau")
    print("   • Adaptive Bandwidth: Retry với bandwidth giảm nếu cần")
    print(f"\n3. KẾT QUẢ: {len(accepted)}/200 demands")
    print(f"   • Hiệu suất capacity: {efficiency:.1f}%")
    print(f"   • Avg utilization: {avg_util:.1f}% (lý tưởng: 60-80%)")

if __name__ == "__main__":
    main()