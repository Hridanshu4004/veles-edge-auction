from common.models import TrustProfile


def update_calibration(tp: TrustProfile, claim, actual_success: bool, actual_latency: float):
    alpha = 0.1  # Slower EMA decay for stability
    
    tp.evidence.observations += 1
    if actual_success:
        tp.evidence.successful_tasks += 1
    else:
        tp.evidence.failed_tasks += 1
        
    # Brier Score for success (0 is perfect, 1 is worst)
    predicted_success = claim.success_probability
    actual_val = 1.0 if actual_success else 0.0
    current_brier = (predicted_success - actual_val) ** 2
    
    if tp.evidence.observations == 1:
        tp.evidence.success_brier_score = current_brier
    else:
        tp.evidence.success_brier_score = (1 - alpha) * tp.evidence.success_brier_score + alpha * current_brier
        
    # MAE for latency (Absolute Error)
    current_error = abs(actual_latency - claim.latency_p50_ms)
    if tp.evidence.observations == 1:
        tp.evidence.latency_mae = current_error
    else:
        tp.evidence.latency_mae = (1 - alpha) * tp.evidence.latency_mae + alpha * current_error
        
    return tp
