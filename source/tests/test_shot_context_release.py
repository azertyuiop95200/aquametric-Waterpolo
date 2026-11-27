import unittest,json
from services.shot_context_review import append,build,point_at
from services.collective_review import context
from test_collective_review_release import fixture

def sample():
    s=fixture();summary=s['automatic']['summary']
    summary['metric_field_map']['shots']=[dict(second=.1,x_m=15,y_m=0,provenance='manual_review_candidate',outcome='goal')]
    summary['identity_reviews']['shots']={'0':dict(side='for',cap_number=2,provenance='coach_review',evidence='QA')}
    s['primary_shot_events']=[dict(id=11,kind='shot_on_target',second=.1,period=1,side='for',identity='for:2'),dict(id=12,kind='save',second=.2,period=1,side='against',identity='against:1')]
    return s

def raw(s):
    return dict(binding=context(s),shot_index=0,event_id=11,save_event_id=12,goal_x=25,goal_width_m=3,defenders=['against:4','against:1'],keeper='against:1',assumed_lateral_span_m=1.,evidence='QA synthetic',shot_link_reviewed=True,roster_reviewed=True)

def saved():
    s=sample();s['automatic']['summary']['shot_context_reviews']=append(s,raw(s));return s

class ShotContextTests(unittest.TestCase):
    def test_build(self):
        r=build(saved(),local_source=True);self.assertEqual(r['status'],'experimental_partial');a=r['rows'][0];self.assertEqual(a['event']['kind'],'shot_on_target');self.assertEqual(a['save']['id'],12);self.assertAlmostEqual(a['distance_to_goal_m'],10);self.assertTrue(a['complete_geometry']);self.assertAlmostEqual(a['keeper']['projected_fraction'],1/2.7);self.assertIsNone(a['goal_probability']);json.dumps(r,allow_nan=False)
    def test_no_inferred_save(self):
        s=sample();w=raw(s);w['save_event_id']=None;s['automatic']['summary']['shot_context_reviews']=append(s,w);self.assertIsNone(build(s,local_source=True)['rows'][0]['save'])
    def test_wrong_identity(self):
        s=sample();s['primary_shot_events'][0]['identity']='for:3';self.assertRaises(ValueError,append,s,raw(s))
    def test_wrong_time(self):
        s=sample();s['primary_shot_events'][0]['second']=2;self.assertRaises(ValueError,append,s,raw(s))
    def test_wrong_period_save(self):
        s=sample();s['primary_shot_events'][1]['period']=2;self.assertRaises(ValueError,append,s,raw(s))
    def test_duplicate(self):
        s=saved();self.assertRaises(ValueError,append,s,raw(s))
    def test_stale_event(self):
        s=saved();s['primary_shot_events'][0]['kind']='shot_off_target';self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_stale_calibration(self):
        s=saved();s['automatic']['summary']['metric_field_map']['revision']='new';self.assertEqual(build(s,local_source=True)['rows'],[])
    def test_missing_defender(self):
        s=saved();s['advanced_motion']['players'][2]['segments']=[];a=build(s,local_source=True)['rows'][0];self.assertFalse(a['complete_geometry']);self.assertIsNone(a['centerline_field_gap_m'])
    def test_remote(self):self.assertEqual(build(saved(),local_source=False)['status'],'unavailable')
    def test_missing_link(self):
        s=sample();w=raw(s);w['shot_link_reviewed']=False;self.assertRaises(ValueError,append,s,w)
    def test_no_extrapolation(self):
        self.assertIsNone(point_at(sample()['advanced_motion']['players'][0],1,25,20))
    def test_primary_source_binding_and_period(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from db import Base
        from models import Event, EventPosition, MatchVideoSegment
        from types import SimpleNamespace
        from services.shot_context_review import primary_events,source_key
        engine=create_engine('sqlite:///:memory:')
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([MatchVideoSegment(id=1,match_id=10,period=1,source_type='upload',video_path='primary.mp4'),MatchVideoSegment(id=2,match_id=10,period=2,source_type='upload',video_path='secondary.mp4')])
            for i,seg,period,mid in [(11,1,1,10),(12,2,2,10),(13,1,2,10),(14,1,1,99),(15,None,1,10)]:
                db.add(Event(id=i,match_id=mid,event_type='goal'))
                db.add(EventPosition(event_id=i,segment_id=seg,period=period,segment_second=.1,provenance='manual_verified'))
            db.commit()
            s=sample();s['verified_events']=[dict(id=i,event_type='goal',perspective='for') for i in range(11,16)]
            s['identity_analysis']={'event_rows':[dict(id=i,review=dict(side='for',cap_number=2,provenance='coach_review')) for i in range(11,16)]}
            m=SimpleNamespace(id=10,video_source='upload',video_path='primary.mp4')
            self.assertEqual(primary_events(db,m,s),[])
            s['automatic']['summary']['metric_field_map']['source_key']=source_key(m.video_path)
            self.assertEqual([x['id'] for x in primary_events(db,m,s)],[11])
            m.video_path='secondary.mp4'
            self.assertEqual(primary_events(db,m,s),[])
        engine.dispose()
if __name__=='__main__':unittest.main()
