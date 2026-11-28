"""Reviewed, source-bound R7 window geometry. Estimates, not match totals.
Reuse production calibration and motion engines. Never promote raw detections.
"""
from pathlib import Path
from math import isfinite
import cv2
from services.r7_review_pipeline import file_hash
from services.metric_field import calibrate,CameraAligner,project,measure
from services.advanced_tracking import motion
from services.occupancy_grid import occupancy,density
from services.identity_aggregation import review_identity

def number(v):return type(v) in (float,int) and isfinite(v)

def select_tracks(scan,raw,roster):
    if scan.get('scan_status','completed')!='completed' or scan.get('coordinate_system')!='image_normalized':
        raise ValueError('Scan indisponible.')
    fps=scan.get('source_fps_reported')
    if not number(fps) or not 10<=fps<=60:raise ValueError('Cadence nominale invalide.')
    if raw.get('all_points_reviewed') is not True or raw.get('calibration_reviewed') is not True or raw.get('nominal_time_acknowledged') is not True:
        raise ValueError('Revoir toutes les positions, identité, repères et temps nominal.')
    period=raw.get('period');ref=raw.get('reference_frame')
    if type(period) is not int or not 1<=period<=8 or type(ref) is not int:raise ValueError('Période ou image de référence invalide.')
    frames=scan.get('frames',[])
    if not isinstance(frames,list) or not 1<=len(frames)<=75:raise ValueError('Fenêtre invalide.')
    by_index={}
    for f in frames:
        i=f.get('source_frame_index');t=f.get('second')
        if type(i) is not int or i<0 or i in by_index or not number(t) or abs(t-i/fps)>1e-5:
            raise ValueError('Indices incohérents.')
        by_index[i]=f
    if ref not in by_index:raise ValueError('Référence hors fenêtre échantillonnée.')
    tracks=scan.get('tracks',[]);by_id={str(t['id']):t for t in tracks}
    if len(by_id)!=len(tracks):raise ValueError('Pistes ambiguës.')
    selected=raw.get('tracks')
    if not isinstance(selected,list) or not 1<=len(selected)<=8:raise ValueError('Choisir 1 à 8 pistes revues.')
    seen=set();people=set();out=[]
    for item in selected:
        k=item.get('track_id')
        if type(k) is not int or str(k) not in by_id or k in seen:raise ValueError('Piste inconnue ou dupliquée.')
        seen.add(k);ident=review_identity(item)
        cap=ident['cap_number'];side=ident['side']
        if cap is None or (side=='for' and roster.count(cap)!=1):raise ValueError('Bonnet non attribuable à la feuille.')
        if (side,cap) in people:raise ValueError('Une piste par identité et fenêtre.')
        people.add((side,cap));tr=by_id[str(k)]
        if tr.get('kind')!='head':raise ValueError('Piste de tête requise.')
        points=[];last=-1
        for p in tr.get('points',[]):
            t,x,y=(p.get(n) for n in ('second','x','y'))
            if not all(map(number,(t,x,y))) or not 0<=x<=1 or not 0<=y<=1:raise ValueError('Point invalide.')
            i=round(t*fps)
            f=by_index.get(i)
            if i<=last or f is None or abs(t-i/fps)>1e-5:raise ValueError('Point hors fenêtre ou temps non croissant.')
            matches=[d for d in f.get('detections',[]) if d.get('track_id')==k and d.get('kind')=='head' and d.get('x')==x and d.get('y')==y]
            if len(matches)!=1:raise ValueError('Point sans observation correspondante.')
            points.append(dict(frame=i,second=i/fps,x=x,y=y));last=i
        if len(points)<5:raise ValueError('Au moins cinq positions revues par piste.')
        out.append(dict(track_id=k,identity=ident,points=points))
    return fps,period,ref,out

def analyze(path,scan,raw,roster):
    fps,period,ref,tracks=select_tracks(scan,raw,roster)
    path=Path(path);stat=path.stat()
    if stat.st_size>1200*1024*1024:raise ValueError('Source trop volumineuse.')
    sha=file_hash(path)
    if sha!=scan.get('source_sha256_at_creation'):raise ValueError('Empreinte de source absente ou différente ; refaire le scan.')
    L,W=raw.get('length_m'),raw.get('width_m')
    if not number(L) or not number(W):raise ValueError('Dimensions invalides.')
    cal=calibrate(raw.get('anchors'),W,L)
    multi=raw.get('additional_references') is not None
    frame_ids=sorted({p['frame'] for t in tracks for p in t['points']})
    if multi and len(frame_ids)>30:raise ValueError('Calibration multiple limitée à 30 images échantillonnées.')
    reference_meta=[];projection_quality=[];cuts={f['source_frame_index'] for f in scan['frames'] if f.get('scene_reset') is True}
    c=cv2.VideoCapture(str(path))
    try:
        if not c.isOpened() or abs(float(c.get(cv2.CAP_PROP_FPS))-fps)>1e-5:raise ValueError('Cadence modifiée.')
        def frame(i):
            if not c.set(cv2.CAP_PROP_POS_FRAMES,i):raise ValueError('Recherche image impossible.')
            ok,f=c.read()
            if not ok or f is None or round(c.get(cv2.CAP_PROP_POS_FRAMES))!=i+1:raise ValueError('Image non vérifiable.')
            return cv2.resize(f,(960,540))
        if multi:
            from services.r7_multireference import references,consensus
            aligner,reference_meta=references(raw,scan,frame,L,W)
        else:aligner=CameraAligner(frame(ref),raw.get('polygon'))
        cache={}
        for i in frame_ids:
            cache[i]=aligner.align(frame(i))
        players=[]
        for t in tracks:
            pts=[];requested=len(t['points']);last_frame=None
            for p in t['points']:
                if last_frame is not None and any(last_frame<cut<=p['frame'] for cut in cuts):pts.append(None)
                last_frame=p['frame']
                a=cache[p['frame']]
                if multi:
                    q=consensus(aligner,a,p['x'],p['y'])
                    xy=(q['x_m'],q['y_m']) if q is not None else None
                    projection_quality.append(dict(track_id=t['track_id'],frame=p['frame'],support=q['support'] if q else 0,spread_m=q['spread_m'] if q else None,accepted=q is not None))
                else:xy=project(cal,*aligner.point(a[0],p['x'],p['y'])) if a is not None else None
                if xy is None or not 0<=xy[0]<=L or not -W/2<=xy[1]<=W/2:pts.append(None)
                else:pts.append(dict(second=p['second'],x_m=xy[0],y_m=xy[1]+W/2))
            measured=measure(pts);segments=measured['segments']
            m=motion(segments,sprint_mps=1.5,min_sprint_s=.35)
            occ=density(occupancy(segments,L,W,2.,0.,86400.)) if m['observed_s'] else None
            players.append(dict(track_id=t['track_id'],identity=t['identity'],requested_points=requested,
                projected_points=sum(p is not None for p in pts),metrics=m,segments=segments,occupation=occ,
                playing_seconds=None))
    finally:c.release()
    end=path.stat()
    if (stat.st_size,stat.st_mtime_ns)!=(end.st_size,end.st_mtime_ns):raise ValueError('Source modifiée pendant la revue.')
    if not any(p['metrics']['observed_s']>0 for p in players):raise ValueError('Aucune trajectoire métrique continue exploitable.')
    return dict(engine='r7-reviewed-metric-multiref-v1' if multi else 'r7-reviewed-metric-v1',
        calibration_mode='multi_reference_consensus' if multi else 'single_reference',reference_details=reference_meta,
        projection_quality=projection_quality,consensus_tolerance_m=.75 if multi else None,
        independent_metric_accuracy_validated=False,status='experimental_partial',period=period,reference_frame=ref,
        source_sha256_at_creation=sha,source_file_size=stat.st_size,source_file_mtime_ns=stat.st_mtime_ns,
        length_m=L,width_m=W,anchors=raw['anchors'],polygon=raw['polygon'],players=players,
        requested_frames=len(cache),aligned_frames=sum((len(a)>=2 if multi else a is not None) for a in cache.values()),
        time_basis='nominal_frame_index_divided_by_reported_fps',pts_validated=False,
        identity_verified=False,metrics_validated=False,statistical_use_allowed=False,
        scope='reviewed_window_not_match_total',note='Projection estimative, positions de tête revues, cadence nominale ; pas de temps de jeu, ni total de match. Ne pas additionner les fenêtres.')
