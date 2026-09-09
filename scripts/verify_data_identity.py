import hashlib
import json
import psycopg

TABLES = [
    "channels",
    "channel_metrics",
    "videos",
    "video_metrics",
    "clusters",
    "cluster_videos",
    "subniches",
    "market_structure_analyses",
    "production_risk_analyses",
    "cluster_profitability_analyses",
    "cluster_validation_analyses",
    "video_outlier_analyses"
]

PRIMARY_KEYS = {
    "channels": ["channel_id"],
    "channel_metrics": ["id"],
    "videos": ["video_id"],
    "video_metrics": ["id"],
    "clusters": ["run_id", "cluster_id"],
    "cluster_videos": ["run_id", "cluster_id", "video_id"],
    "subniches": ["id"],
    "market_structure_analyses": ["id"],
    "production_risk_analyses": ["id"],
    "cluster_profitability_analyses": ["id"],
    "cluster_validation_analyses": ["id"],
    "video_outlier_analyses": ["id"]
}

def serialize_val(v):
    if v is None:
        return None
    return str(v)

def get_table_data(conn, table_name, pk_cols):
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {table_name}")
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    
    data_map = {}
    row_hashes = []
    
    for row in rows:
        row_dict = {cols[i]: serialize_val(row[i]) for i in range(len(cols))}
        pk_val = tuple(row_dict[k] for k in pk_cols)
        row_str = json.dumps(row_dict, sort_keys=True)
        h = hashlib.sha256(row_str.encode('utf-8')).hexdigest()
        data_map[pk_val] = (row_dict, h)
        row_hashes.append(h)
        
    row_hashes.sort()
    table_hash = hashlib.sha256("".join(row_hashes).encode('utf-8')).hexdigest()
    return len(rows), data_map, table_hash

def main():
    conn_src = psycopg.connect('postgresql://postgres:prytb@localhost:5433/insforge_restore')
    conn_tgt = psycopg.connect('postgresql://postgres:prytb@localhost:5433/prytb')

    print(f"{'TABLE':<32} | {'SRC':<6} | {'TGT':<6} | {'MISS':<5} | {'EXTRA':<5} | {'MOD':<5} | {'MATCH':<5}")
    print("-" * 80)

    all_pass = True
    for table in TABLES:
        pk_cols = PRIMARY_KEYS[table]
        src_cnt, src_map, src_hash = get_table_data(conn_src, table, pk_cols)
        tgt_cnt, tgt_map, tgt_hash = get_table_data(conn_tgt, table, pk_cols)
        
        src_keys = set(src_map.keys())
        tgt_keys = set(tgt_map.keys())
        
        missing_keys = src_keys - tgt_keys
        extra_keys = tgt_keys - src_keys
        
        common_keys = src_keys & tgt_keys
        modified_keys = set()
        for k in common_keys:
            if src_map[k][1] != tgt_map[k][1]:
                modified_keys.add(k)
                
        match = (src_cnt == tgt_cnt) and (len(missing_keys) == 0) and (len(extra_keys) == 0) and (len(modified_keys) == 0) and (src_hash == tgt_hash)
        if not match:
            all_pass = False
            
        print(f"{table:<32} | {src_cnt:<6} | {tgt_cnt:<6} | {len(missing_keys):<5} | {len(extra_keys):<5} | {len(modified_keys):<5} | {'PASS' if match else 'FAIL':<5}")

    print("-" * 80)
    print("ALL TABLES IDENTITY RECONCILIATION:", "PASS" if all_pass else "FAIL")
    
    # Check outlier counts
    cur_tgt = conn_tgt.cursor()
    cur_tgt.execute("SELECT count(*) FROM video_outlier_analyses WHERE is_strong_outlier = true")
    actual_outliers = cur_tgt.fetchone()[0]
    
    cur_tgt.execute("SELECT count(*) FROM video_outlier_analyses WHERE small_channel_outlier = true")
    small_channel_outliers = cur_tgt.fetchone()[0]
    print(f"OUTLIERS AUDIT: actual={actual_outliers} (expected 528), small_channel={small_channel_outliers} (expected 230)")

    conn_src.close()
    conn_tgt.close()

if __name__ == "__main__":
    main()
