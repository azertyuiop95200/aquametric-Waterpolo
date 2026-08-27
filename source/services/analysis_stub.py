"""Honest placeholder for future AI workers.
It never fabricates sports events. It only validates that a match is ready for external AI processing.
"""

def baseline_analysis_message(match):
    if not (match.video_url or match.video_path):
        return "No video source available."
    return (
        "Video accepted. The web product layer is ready, but no computer-vision model is connected yet. "
        "No automatic events or physical metrics were fabricated."
    )
