from langchain.tools import tool


@tool
def compare_performance(run_id: str, baseline_run_id: str): 
    
    baseline_run_metrics = get_run(baseline_run_id)
    current_run_metrics = get_run(run_id)

    deltas = compute_deltas(current_run_metrics, baseline_run_metrics)
