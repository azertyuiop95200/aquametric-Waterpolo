"""One-to-one head-position benchmark in pixel coordinates.
Reference annotations must be independent of detector predictions.
"""
import math
def evaluate(reference,predicted,tolerance_px=20):
    edges=[[j for j in sorted(range(len(predicted)),key=lambda j:math.dist(p,predicted[j])) if math.dist(p,predicted[j])<=tolerance_px] for p in reference]
    matched={}
    def augment(i,seen):
        for j in edges[i]:
            if j in seen:continue
            seen.add(j)
            if j not in matched or augment(matched[j],seen):matched[j]=i;return True
        return False
    for i in range(len(reference)):augment(i,set())
    tp=len(matched);fp=len(predicted)-tp;fn=len(reference)-tp
    return {'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'matches':[(i,j) for j,i in matched.items()]}
