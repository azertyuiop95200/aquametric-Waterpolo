"""Validate the private evidence index, never dereference uploaded paths on the server."""
import re

def require(ok,message):
    if not ok: raise ValueError(message)

def validate_manifest(reference):
    rows=reference.get('evidence_manifest')
    if rows is None:return None
    require(isinstance(rows,list) and 1<=len(rows)<=10000,'Manifeste de preuves invalide.')
    events={e['event_id'] for e in reference.get('events',[])}
    intervals={e['interval_id'] for e in reference.get('possession_review_intervals',[])}
    passes={e['id']:e for e in (reference.get('pass_review') or {}).get('actions',[])}
    require(not (events&intervals or events&passes.keys() or intervals&passes.keys()),'Identifiants de preuves ambigus.')
    keys=set();paths={};coverage=set();pass_paths=set()
    for r in rows:
        require(isinstance(r,dict),'Entrée de manifeste invalide.')
        uid,kind,path,digest,size=(r.get(k) for k in ('id','kind','path','sha256','bytes'))
        require(isinstance(uid,str) and isinstance(kind,str),'Identifiant ou type de preuve invalide.')
        require((uid in events and kind in {'source','later_control_evidence','immediate_evidence','correction'}) or (uid in intervals and kind in {'interval','correction'}) or (uid in passes and kind=='pass'),'Preuve non rattachée à une action.')
        require(isinstance(path,str) and len(path)<=240 and path.startswith(('preuves/','preuves_consolidees/')) and re.fullmatch(r'[A-Za-z0-9_./-]+\.jpg',path) and all(x not in {'','.','..'} for x in path.split('/')),'Chemin de preuve invalide.')
        require(isinstance(digest,str) and re.fullmatch(r'[a-f0-9]{64}',digest) and type(size) is int and 0<size<=100*1024*1024,'Empreinte ou taille de preuve invalide.')
        key=(uid,kind,path);require(key not in keys,'Entrée de preuve dupliquée.');keys.add(key)
        signature=(digest,size);require(path not in paths or paths[path]==signature,'Empreintes contradictoires pour un fichier.');paths[path]=signature
        coverage.add((uid,kind))
        if kind=='pass':pass_paths.add((uid,path))
    require(all((uid,'source') in coverage for uid in events) and all((uid,'interval') in coverage for uid in intervals),'Preuve source ou intervalle manquante.')
    require(all((uid,path) in pass_paths for uid,a in passes.items() for path in a['evidence']),'Preuve de passe absente du manifeste.')
    return dict(entries=len(rows),distinct_paths=len(paths),declared_bytes=sum(v[1] for v in paths.values()),files_verified_on_server=False,note='Empreintes déclarées contrôlées syntaxiquement ; les images privées ne sont pas lues ni vérifiées par le serveur.')
