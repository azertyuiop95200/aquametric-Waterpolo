"""Offline, frame-bound detector comparisons. No automatic statistical promotion."""
import hashlib,json,math,re
from collections import Counter
from services.detection_evaluation import evaluate_points

GEOMETRIES={'head_center':'point','ball_center':'point','player_box':'box','goal_box':'box'}
LIMITS={'head_center':22,'ball_center':15,'player_box':.5,'goal_box':.5}
VERSION='aquametric-offline-benchmark-v1'

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def require(ok,message):
    if not ok:raise ValueError(message)

def ishash(s):return isinstance(s,str) and re.fullmatch('[a-f0-9]{64}',s) is not None

def geometry(kind,coords):
    n=2 if GEOMETRIES[kind]=='point' else 4
    require(isinstance(coords,list) and len(coords)==n and all(type(v) in (float,int) and math.isfinite(v) and 0<=v<=1 for v in coords),'Coordonnées normalisées invalides')
    if n==4:require(coords[0]<coords[2] and coords[1]<coords[3],'Boîte dégénérée')

def manifest(frames):
    require(isinstance(frames,list) and 1<=len(frames)<=500,'Nombre d’images invalide')
    seen=set();rows=[]
    for r in frames:
        require(isinstance(r,dict),'Image invalide')
        s,i,h,w,d=(r.get(k) for k in ('source_sha256','frame_index','height','width','image_sha256'))
        require(ishash(s) and ishash(d) and type(i) is int and i>=0 and type(h) is int and type(w) is int and 128<=h<=2160 and 128<=w<=3840,'Métadonnées invalides')
        key=f'{s}:{i}';require(key not in seen,'Image dupliquée');seen.add(key)
        rows.append(dict(frame_id=key,source_sha256=s,frame_index=i,height=h,width=w,image_sha256=d))
    m=dict(version=VERSION,image_hash_basis='decoded_BGR_uint8_C_order',frames=sorted(rows,key=lambda x:x['frame_id']),thresholds=LIMITS.copy())
    return dict(m,manifest_sha256=digest(m))

def checked_manifest(m):
    require(isinstance(m,dict) and isinstance(m.get('frames'),list),'Manifeste invalide')
    require(manifest(m['frames'])==m,'Manifeste modifié ou incompatible')
    return {r['frame_id']:r for r in m['frames']}

def _rows(data,frames):
    require(isinstance(data,list) and len(data)==len(frames),'Une réponse explicite par image est requise')
    out={}
    for row in data:
        require(isinstance(row,dict) and isinstance(row.get('frame_id'),str),'Identifiant image invalide')
        key=row['frame_id'];require(key in frames and key not in out and row.get('image_sha256')==frames[key]['image_sha256'],'Image absente, dupliquée ou empreinte incompatible')
        out[key]=row
    return out

def _iou(a,b):
    intersection=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return intersection/((a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-intersection)

def _boxes(ref,pred,threshold):
    links={i:sorted((-_iou(a,b),j) for j,b in enumerate(pred) if _iou(a,b)>=threshold) for i,a in ref.items()};assigned={}
    def visit(i,seen):
        for _,j in links[i]:
            if j in seen:continue
            seen.add(j)
            if j not in assigned or visit(assigned[j],seen):assigned[j]=i;return True
        return False
    for i in sorted(ref):visit(i,set())
    return {i:dict(prediction_index=j,iou=round(_iou(ref[i],pred[j]),6)) for j,i in assigned.items()}

def evaluate(m,references,submission):
    """References stay private; submission claims inference on manifest images, not proof.
    Only declared compatible geometries compared; unknown and incomplete references stay separate.
    """
    frames=checked_manifest(m)
    for data in (references,submission):
        require(isinstance(data,dict) and data.get('manifest_sha256')==m['manifest_sha256'],'Manifeste de référence incompatible')
    model=submission.get('model_id');supported=submission.get('supported_geometries')
    require(isinstance(model,str) and 0<len(model)<=150 and isinstance(supported,list) and 1<=len(supported)<=len(GEOMETRIES) and all(isinstance(k,str) and k in GEOMETRIES for k in supported) and len(set(supported))==len(supported),'Modèle ou géométries invalides')
    rr=_rows(references.get('frames'),frames);pp=_rows(submission.get('frames'),frames);results=[]
    for key,f in frames.items():
        ref=rr[key].get('reference');pred=pp[key].get('predictions')
        require(isinstance(ref,dict) and all(k in GEOMETRIES for k in ref) and isinstance(pred,dict) and set(pred)==set(supported),'Classes absentes ou incompatibles')
        for k,items in pred.items():
            require(isinstance(items,list) and len(items)<=100,'Trop de propositions')
            for coords in items:geometry(k,coords)
        for k,r in ref.items():
            require(isinstance(r,dict) and r.get('completeness') in ('partial','complete','unknown') and isinstance(r.get('objects'),dict) and len(r['objects'])<=100,'Référence invalide')
            state=r['completeness'];objects=r['objects']
            require(state!='unknown' or not objects,'Référence inconnue non vide')
            for i,coords in objects.items():
                require(isinstance(i,str) and 0<len(i)<=100,'Identifiant invalide');geometry(k,coords)
            if k not in supported or state=='unknown':
                results.append(dict(frame_id=key,geometry=k,completeness=state,status='unsupported_geometry' if k not in supported else 'unknown_reference'));continue
            preds=pred[k]
            if GEOMETRIES[k]=='point':
                def px(p):return [p[0]*f['width'],p[1]*f['height']]
                matched=evaluate_points({i:px(p) for i,p in objects.items()},[px(p) for p in preds],LIMITS[k],completeness=state)['matches']
            else:matched=_boxes(objects,preds,LIMITS[k])
            results.append(dict(frame_id=key,geometry=k,completeness=state,status='evaluated',marked=len(objects),matched=len(matched),predictions=len(preds),matches=matched,first_ball_candidate_matched=(bool(preds) and math.dist(px(next(iter(objects.values()))),px(preds[0]))<=LIMITS[k] if k=='ball_center' and len(objects)==1 else None)))
    summary={}
    for k in GEOMETRIES:
        rows=[r for r in results if r['geometry']==k];evaluated=[r for r in rows if r['status']=='evaluated'];complete=[r for r in evaluated if r['completeness']=='complete'];partial=[r for r in evaluated if r['completeness']=='partial']
        def totals(rs):
            a={v:sum(r[v] for r in rs) for v in ('marked','matched','predictions')};a['frames']=len(rs);a['recall']=a['matched']/a['marked'] if a['marked'] else None;return a
        c=totals(complete);p=totals(partial);c['precision']=c['matched']/c['predictions'] if c['predictions'] else None;p['precision']=None
        summary[k]=dict(status_counts=dict(Counter(r['status'] for r in rows)),complete=c,partial=p,first_ball_candidate_matched=sum(r['first_ball_candidate_matched'] is True for r in evaluated),first_ball_candidate_denominator=sum(r['first_ball_candidate_matched'] is not None for r in evaluated))
    return dict(version=VERSION,manifest_sha256=m['manifest_sha256'],reference_sha256=digest(references),model_id=model,summary=summary,rows=results,source_pixels_verified_by_evaluator=False,model_provenance_verified=False,statistical_use_allowed=False,note='Comparaison hors ligne de propositions déclarées; précision uniquement sur références complètes, aucun événement ni identité validé.')
