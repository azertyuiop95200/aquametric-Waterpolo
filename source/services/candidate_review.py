"""Private active-learning review packets. No automatic promotion to reference data."""
import hashlib,json,math,re
from services.learned_head import review_disagreements

VERSION='head-candidate-review-v1'

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def _hash(s):return isinstance(s,str) and re.fullmatch('[a-f0-9]{64}',s) is not None

def make_packet(source_sha256,frame_index,image_sha256,width,height,baseline,learned,*,budget=3):
    if not _hash(source_sha256) or not _hash(image_sha256):raise ValueError('Empreintes source/image invalides.')
    if type(frame_index) is not int or frame_index<0:raise ValueError('Indice source invalide.')
    review=review_disagreements(baseline,learned,width,height,extra_limit=budget)
    rows=[]
    for i,d in enumerate(review['additional_review_candidates']):
        rows.append(dict(candidate_id=f'C{i+1:02d}',x=round(float(d['x']),8),y=round(float(d['y']),8),origin='learned_only'))
    packet=dict(version=VERSION,source_sha256=source_sha256,source_frame_index=frame_index,image_sha256=image_sha256,width=width,height=height,budget=budget,baseline_count=len(baseline),candidates=rows,statistical_use_allowed=False)
    return dict(packet,packet_sha256=digest(packet))

def validate_response(packet,response):
    if not isinstance(packet,dict) or not isinstance(response,dict):raise ValueError('Paquet/réponse invalide.')
    expected=packet.get('packet_sha256')
    try: actual=digest({k:v for k,v in packet.items() if k!='packet_sha256'})
    except (TypeError,ValueError,OverflowError):raise ValueError('Paquet non sérialisable.') from None
    if not _hash(expected) or actual!=expected or response.get('packet_sha256')!=expected:raise ValueError('Paquet modifié ou réponse incompatible.')
    if packet.get('version')!=VERSION or packet.get('statistical_use_allowed') is not False:raise ValueError('Version invalide.')
    w,h,budget,count=(packet.get(k) for k in ('width','height','budget','baseline_count'))
    if not _hash(packet.get('source_sha256')) or not _hash(packet.get('image_sha256')) or type(packet.get('source_frame_index')) is not int or packet['source_frame_index']<0:raise ValueError('Source invalide.')
    if not all(type(v) is int for v in (w,h,budget,count)) or not 128<=w<=3840 or not 128<=h<=2160 or not .8<=w/h<=3.2 or not 0<=budget<=6 or not 0<=count<=24:raise ValueError('Métadonnées hors limites.')
    rows=packet.get('candidates');decisions=response.get('decisions')
    if not isinstance(rows,list) or len(rows)>budget or not isinstance(decisions,list) or len(decisions)>len(rows):raise ValueError('Décisions hors limites.')
    for i,r in enumerate(rows):
        if not isinstance(r,dict) or r.get('candidate_id')!=f'C{i+1:02d}' or r.get('origin')!='learned_only' or not all(type(r.get(k)) in (int,float) and math.isfinite(r[k]) and 0<=r[k]<=1 for k in ('x','y')):raise ValueError('Candidat invalide.')
    ids={r['candidate_id'] for r in rows};seen=set();out=[]
    if len(ids)!=len(rows):raise ValueError('Identifiants dupliqués.')
    for d in decisions:
        if not isinstance(d,dict):raise ValueError('Décision invalide.')
        k=d.get('candidate_id');label=d.get('label')
        if not isinstance(k,str) or k not in ids or k in seen or not isinstance(label,str) or label not in ('head_present','not_head','uncertain'):raise ValueError('Décision invalide ou dupliquée.')
        seen.add(k);out.append(dict(candidate_id=k,label=label))
    counts={k:sum(d['label']==k for d in out) for k in ('head_present','not_head','uncertain')}
    return dict(packet_sha256=expected,decisions=out,counts=counts,unreviewed=len(rows)-len(out),complete=len(out)==len(rows),reviewer_verified_by_server=False,training_labels_require_verification=True,statistical_use_allowed=False)
