# --- Helper function to generate the yard report ---
def generate_yard_report(yard_stores, yc_string_map):
    """Creates a formatted string showing the contents of each yard block."""
    report_lines = []
    total_containers = 0
    for block_id, store in enumerate(yard_stores):
        block_name = yc_string_map.get(block_id, f"Block_{block_id+1}")
        report_lines.append(f"--- {block_name} (Block {block_id}) ---")
        if not store.items:
            report_lines.append("  (empty)")
        else:
            for container in store.items:
                report_lines.append(f"  - {container.id} ({container.mass/1000:.1f}t, {container.type})")
        total_containers += len(store.items)
    report_lines.insert(0, f"Total Containers in Yard: {total_containers}")
    report_lines.insert(0, "="*40)
    report_lines.append("="*40)
    return "\n".join(report_lines)

# --- Helper function to generate the operations report ---
def generate_yard_operations_report(all_yc_agents, yc_agent_working_stats, run_time):
    """Aggregates and prints the total number of yard operations."""
    total_stores = 0
    total_retrieves = 0
    total_rehandles = 0
    ycs = 0
    total_time = 0

    # Iterate through all the crane agents to get their final counts
    for crane in all_yc_agents.values():
        total_stores += crane.store_count
        total_retrieves += crane.retrieve_count
        total_rehandles += crane.rehandle_count
        
    for yc_id, logged_operations in yc_agent_working_stats.items():
        ycs +=1
        for log_entry in logged_operations:
            _, _, yc_hndl_time = log_entry
            total_time += yc_hndl_time
    
    # Calculate summary statistics
    total_productive = total_stores + total_retrieves
    total_moves = total_productive + total_rehandles
    rehandle_ratio = (total_rehandles / total_moves) * 100 if total_productive > 0 else 0
    util_rate = total_time / ycs / run_time * 100

    # Format the report string
    report_lines = []
    report_lines.append("="*40)
    report_lines.append("--- Yard Operations Summary ---")
    report_lines.append(f"  Total Productive Moves: {total_productive}")
    report_lines.append(f"    - Stores: {total_stores}")
    report_lines.append(f"    - Retrieves: {total_retrieves}")
    report_lines.append(f"  Total Non-Productive Re-handles: {total_rehandles}")
    report_lines.append(f"  Total Moves: {total_moves}")
    report_lines.append(f"  Utilization Rate: {util_rate:.2f} %")
    report_lines.append(f"  Re-handle Ratio (Housekeeping/Total): {rehandle_ratio:.2f}%")
    return "\n".join(report_lines)

# --- Helper function to generate the operations report ---
def generate_quay_operations_report(qc_working, run_time):
    """Aggregates and prints the total number of yard operations."""
    total_export = 0
    total_import = 0
    qcs = 0
    total_time = 0

    # Iterate through all the crane agents to get their final counts
    for qc_id, logged_operations in qc_working.items():
        qcs +=1
        for log_entry in logged_operations:
            _, _, qc_hndl_time, op_type = log_entry
            if op_type == "IMPORT":
                total_import += 1
            elif op_type == "EXPORT":
                total_export +=1
            total_time += qc_hndl_time
    
    # Calculate summary statistics
    total_productive = total_export + total_import
    throughput = total_productive / run_time * 60
    util_rate = total_time / qcs / run_time * 100

    # Format the report string
    report_lines = []
    report_lines.append("--- Quay Operations Summary ---")
    report_lines.append(f"  Total (Productive) Moves: {total_productive}")
    report_lines.append(f"    - Export: {total_export}")
    report_lines.append(f"    - Import: {total_import}")
    report_lines.append(f"  Operational Throughput: {throughput:.2f} containers/min")
    report_lines.append(f"  Utilization Rate: {util_rate:.2f} %")
    report_lines.append("="*40)
    return "\n".join(report_lines)