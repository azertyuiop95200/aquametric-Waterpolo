import json, hashlib
from types import SimpleNamespace
from services.review_reference_import import load
from services.private_review_export import collect
from test_review_reference_import import fixture


def test_only_hash_bound_private_files(tmp_path):
    p=fixture();data=b'proof bytes';sha=hashlib.sha256(data).hexdigest()
    p['reference']['evidence_manifest']=[dict(id='G1',kind='source',path='preuves/goal.jpg',sha256=sha,bytes=len(data)),dict(id='P1',kind='interval',path='preuves/control.jpg',sha256=sha,bytes=len(data))]
    _,canonical,digest,period=load(json.dumps(p).encode())
    m=SimpleNamespace(id=1,review_references=[SimpleNamespace(digest=digest,period=period,payload_json=canonical)])
    base=tmp_path/'review_references'/'1'/digest/'preuves';base.mkdir(parents=True)
    (base/'goal.jpg').write_bytes(data);(base/'control.jpg').write_bytes(b'wrong bytes')
    links,files=collect(m,tmp_path)
    assert len(files)==1 and links[digest]['G1'] and 'P1' not in links[digest]
    (base/'goal.jpg').unlink();outside=tmp_path/'outside.jpg';outside.write_bytes(data);(base/'goal.jpg').symlink_to(outside)
    assert not collect(m,tmp_path)[1]
