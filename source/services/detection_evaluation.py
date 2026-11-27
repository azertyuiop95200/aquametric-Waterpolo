"""One-to-one point evaluation; partial references do not establish precision.
Track endpoint continuity is not whole-track identity accuracy.
"""
from math import hypot, isfinite


def _point(p):
    if not isinstance(p, (list, tuple)) or len(p) != 2 or not all(type(v) in (int,float) and isfinite(v) for v in p):
        raise ValueError('Point fini en pixels requis.')
    return p


def evaluate_points(reference, predictions, tolerance_px, *, completeness='partial'):
    if completeness not in {'partial','complete','unknown'}:
        raise ValueError('Couverture invalide.')
    if type(tolerance_px) not in (int,float) or not isfinite(tolerance_px) or tolerance_px <= 0:
        raise ValueError('Tolérance positive requise.')
    if not isinstance(reference,dict) or not isinstance(predictions,list) or len(reference)>100 or len(predictions)>500:
        raise ValueError('Registre invalide.')
    for key,p in reference.items():
        if not isinstance(key,str) or not key:raise ValueError('Identifiant invalide.')
        _point(p)
    for p in predictions:_point(p)
    if completeness=='unknown':
        if reference:raise ValueError('Référence inconnue non vide.')
        return dict(evaluated=False,completeness=completeness,marked=0,predictions=len(predictions),matches={},matched=None,missed=None,unmatched_predictions=None,precision=None,recall=None)
    # Maximum cardinality matching, deterministic proximity order; not minimum cost.
    links={i:sorted((hypot(x-p[0],y-p[1]),j) for j,p in enumerate(predictions) if hypot(x-p[0],y-p[1])<=tolerance_px) for i,(x,y) in reference.items()}
    assigned={}
    def assign(i,seen):
        for _,j in links[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or assign(assigned[j],seen):assigned[j]=i;return True
        return False
    for i in sorted(reference):assign(i,set())
    matches={i:dict(prediction_index=j,error_px=round(hypot(reference[i][0]-predictions[j][0],reference[i][1]-predictions[j][1]),4)) for j,i in assigned.items()}
    n=len(matches)
    return dict(evaluated=True,completeness=completeness,marked=len(reference),predictions=len(predictions),matches=matches,matched=n,missed=len(reference)-n,unmatched_predictions=len(predictions)-n,precision=n/len(predictions) if completeness=='complete' and predictions else None,recall=n/len(reference) if reference else None)


def endpoint_continuity(start_ref,end_ref,start_predictions,end_predictions,tolerance_px):
    """Predictions have point and track_id. IDs must be unique within each frame."""
    def evaluate(ref,preds):
        ids=[p['track_id'] for p in preds]
        if any(type(i) is not int or i<1 for i in ids) or len(set(ids))!=len(ids):raise ValueError('Identifiants de piste invalides.')
        result=evaluate_points(ref,[p['point'] for p in preds],tolerance_px)
        return {key:ids[m['prediction_index']] for key,m in result['matches'].items()}
    a=evaluate(start_ref,start_predictions);b=evaluate(end_ref,end_predictions)
    shared=sorted(set(start_ref)&set(end_ref));rows=[]
    reverse={i:k for k,i in a.items()}
    for k in shared:
        x,y=a.get(k),b.get(k)
        if x is None or y is None:status='missing_endpoint'
        elif x==y:status='same_track_id'
        elif y in reverse and reverse[y]!=k:status='contradictory_endpoint_link'
        else:status='different_track_id'
        rows.append(dict(reference_id=k,start_track_id=x,end_track_id=y,status=status))
    counts={s:sum(r['status']==s for r in rows) for s in ('missing_endpoint','same_track_id','different_track_id','contradictory_endpoint_link')}
    both=len(rows)-counts['missing_endpoint']
    return dict(shared_reference_ids=len(rows),both_endpoints_matched=both,**counts,endpoint_retention=counts['same_track_id']/both if both else None,rows=rows,note='Concordance des identifiants aux deux bornes uniquement, pas une validation des identités intermédiaires.')


def compare_frame_methods(frames, tolerance_px):
    """Paired head-point benchmark on identical independently reviewed frames.

    Frame keys must identify source and frame externally. Missing output is
    not an empty detection. Partial annotations contribute recall only.
    No track identity or sporting statistic is inferred.
    """
    totals = {m: dict(matched=0, marked=0, complete_matched=0,
                      complete_marked=0, complete_predictions=0)
              for m in ("baseline", "head_flow")}
    seen = set()
    paired = complete = partial = 0
    excluded = {"missing_output": 0, "unknown_reference": 0}
    for frame in frames:
        key = frame["frame_key"]
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError("Duplicate or invalid frame key")
        seen.add(key)
        coverage = frame["completeness"]
        if coverage not in ("complete", "partial", "unknown"):
            raise ValueError("Invalid reference coverage")
        if coverage == "unknown":
            excluded["unknown_reference"] += 1
            continue
        if any(frame.get(m) is None for m in totals):
            excluded["missing_output"] += 1
            continue
        paired += 1
        complete += coverage == "complete"
        partial += coverage == "partial"
        for m, t in totals.items():
            result = evaluate_points(frame["reference"], frame[m], tolerance_px,
                                     completeness=coverage)
            t["matched"] += result["matched"]
            t["marked"] += result["marked"]
            if coverage == "complete":
                t["complete_matched"] += result["matched"]
                t["complete_marked"] += result["marked"]
                t["complete_predictions"] += result["predictions"]
    for t in totals.values():
        n, p, a = t["complete_matched"], t["complete_predictions"], t["complete_marked"]
        t["precision"] = n/p if p else None
        t["recall_complete"] = n/a if a else None
        t["recall_reviewed"] = t["matched"]/t["marked"] if t["marked"] else None
        t["f1_complete"] = 2*n/(p+a) if p+a else None
    return dict(version="paired-head-v1", paired_frames=paired,
                complete_frames=complete, partial_frames=partial,
                excluded=excluded, methods=totals, tolerance_px=tolerance_px,
                state="reviewed_sample" if paired else "not_measured")


def compare_scan_windows(baseline, head_flow, references, tolerance_px, *, width=None, height=None):
    """Compare persisted vision-scan-v1 windows; references use exact local frame indices.

    The binding is metadata only, not a byte hash. A reviewer must independently
    establish that the referenced images really belong to this source. Coordinates
    are normalized by the scanner and converted to supplied original pixels here.
    """
    import hashlib
    import json
    from collections import Counter

    references=list(references)
    if width is None and height is None and not references:
        # Candidate-only audit in normalized coordinates; no matching performed.
        width=height=1
    elif type(width) is not int or type(height) is not int or not (128<=width<=3840 and 128<=height<=2160):
        raise ValueError("Invalid reviewed image dimensions")
    if type(tolerance_px) not in (int,float) or not isfinite(tolerance_px) or tolerance_px<=0:
        raise ValueError("Invalid tolerance")
    def unpack(record,mode):
        if record.get("schema")!="vision-scan-v1" or record.get("kind")!="tracklets":
            raise ValueError("Unsupported scan evidence")
        payload={k:v for k,v in record.items() if k not in ("id","digest","segment_id")}
        raw=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)
        if hashlib.sha256(raw.encode()).hexdigest()!=record.get("digest"):
            raise ValueError("Scan digest mismatch")
        r=record["result"]
        if r.get("tracking_mode")!=mode or r.get("coordinate_system")!="image_normalized":
            raise ValueError("Incompatible scan mode or coordinates")
        if r.get("object_scope")!=("heads_only" if mode=="head_flow" else "heads_and_ball_candidates"):
            raise ValueError("Incompatible object scope")
        if any(r.get(k) is True for k in ("identity_verified","metrics_validated","statistical_use_allowed")):
            raise ValueError("Unexpected promotion")
        if r.get("time_basis")!="nominal_frame_index_divided_by_reported_fps":
            raise ValueError("Unsupported time basis")
        fps=r["source_fps_reported"]; first=r["first_frame"]; end=r["end_frame_exclusive"]; stride=r["sample_stride"]
        if type(fps) not in (int,float) or not isfinite(fps) or not 10<=fps<=60:
            raise ValueError("Invalid fps")
        if any(type(x) is not int for x in (first,end,stride)) or not 0<=first<end<=r["source_frame_count_reported"] or not 1<=end-first<=75 or stride<1:
            raise ValueError("Invalid scan window")
        expected=list(range(first,end,stride))
        if [row.get("source_frame_index") for row in r["frames"]]!=expected:
            raise ValueError("Missing or duplicated scan frames")
        points={}
        for row in r["frames"]:
            index=row["source_frame_index"]
            if type(row.get("second")) not in (int,float) or not isfinite(row["second"]) or abs(row["second"]-index/fps)>1e-5:
                raise ValueError("Inconsistent nominal timestamp")
            detector=[]; propagated=[]; signatures=[]
            for d in row["detections"]:
                if d.get("kind")!="head":continue
                x,y=_point([d["x"],d["y"]])
                if not 0<=x<=1 or not 0<=y<=1:raise ValueError("Outside normalized image")
                source=d.get("point_source","detector" if mode=="baseline" else None)
                if source=="detector":
                    detector.append([x*width,y*height])
                    signatures.append((x,y,d.get("colour")))
                elif source=="optical_flow" and mode=="head_flow":propagated.append([x*width,y*height])
                else:raise ValueError("Unknown point provenance")
            points[index]=(detector,propagated,Counter(signatures))
        return r,points
    a,ap=unpack(baseline,"baseline");b,bp=unpack(head_flow,"head_flow")
    for k in ("source_binding","source_file_size","source_file_mtime_ns","segment_id"):
        if baseline.get(k)!=head_flow.get(k):raise ValueError("Different source bindings")
    for k in ("source_fps_reported","source_frame_count_reported","first_frame","end_frame_exclusive","sample_stride"):
        if a[k]!=b[k]:raise ValueError("Different scan windows")
    if not baseline.get("source_binding"):raise ValueError("Missing source binding")
    ref_by_index={}
    for ref in references:
        if ref.get("source_binding")!=baseline["source_binding"] or ref.get("image_width")!=width or ref.get("image_height")!=height:
            raise ValueError("Reference source or dimensions mismatch")
        i=ref["source_frame_index"]
        if type(i) is not int or i<0 or i in ref_by_index:raise ValueError("Duplicate or invalid reference frame")
        ref_by_index[i]=ref
    paired=[]; detector_only=[]; counts=Counter()
    for i,(base,_,base_signature) in ap.items():
        det,flow,flow_signature=bp[i]
        counts["same_detector_candidate_frames"]+=base_signature==flow_signature
        counts.update(baseline_heads=len(base),head_flow_detector_heads=len(det),head_flow_propagated_heads=len(flow))
        ref=ref_by_index.get(i)
        if ref is None:continue
        row=dict(frame_key=str(i),completeness=ref["completeness"],reference=ref["reference"],baseline=base)
        paired.append(dict(row,head_flow=det+flow))
        detector_only.append(dict(row,head_flow=det))
    return dict(version="persisted-head-paired-v1",sampled_frames=len(ap),
                same_detector_candidate_frames=counts["same_detector_candidate_frames"],
                reference_frames_in_window=len(paired),reference_frames_outside_window=len(set(ref_by_index)-set(ap)),
                candidate_counts={k:counts[k] for k in ("baseline_heads","head_flow_detector_heads","head_flow_propagated_heads")},
                all_candidates=compare_frame_methods(paired,tolerance_px),
                detector_only=compare_frame_methods(detector_only,tolerance_px),
                source_binding_state="metadata_only",pts_validated=False,statistical_use_allowed=False,
                note="Frame indices and dimensions are supplied or reported; independent source alignment still required. Propagated points are not independent detections.")
