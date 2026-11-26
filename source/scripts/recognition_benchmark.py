"""Generate an explicitly synthetic report to regression-test recognition metrics."""
import json
from pathlib import Path
from services.recognition_quality import evaluate, audit
from jinja2 import Environment, FileSystemLoader

def main():
    root=Path(__file__).resolve().parents[1]
    out=root/"test-output"
    out.mkdir(exist_ok=True)
    def e(t,kind,side):
        return {"second":t,"event_type":kind,"side":side,"counted":True,"cap_number":4}
    ref=[e(10,"goal","for"),e(18,"shot_off_target","against"),e(25,"interception","for")]
    pred=[e(10.5,"goal","for"),e(17.5,"shot_off_target","against"),e(18,"shot_off_target","against")]
    result=evaluate(ref,pred)
    assert (result["tp"],result["fp"],result["fn"])==(2,1,1)
    quality=audit({"same_source_timeline":True,"observations":[],"candidates":[{"event_type":"goal_candidate_home","evidence":{"bracket_start_second":9,"bracket_end_second":12}}]}, {"events":pred})
    assert quality["time_matches"]==1
    env=Environment(loader=FileSystemLoader(root/"templates"),autoescape=True)
    body=env.get_template("_recognition_quality.html").render(snapshot={"recognition_quality":quality})
    assert "Contrôle qualité" in body and "Concordances temporelles" in body
    (out/"recognition.json").write_text(json.dumps({"synthetic":True,"metrics":result,"quality":quality},indent=2),encoding="utf-8")
    (out/"recognition.html").write_text("<!doctype html><html lang='fr'><meta charset='utf-8'><title>Test synthétique AquaMetric</title><h1>Rapport QA synthétique — aucun match réel</h1>"+body+"<pre>"+json.dumps(result,indent=2)+"</pre></html>",encoding="utf-8")
    print(json.dumps(result))
if __name__=="__main__":
    main()
