"""Exercise the actual review POST, actual snapshot and actual HTML handlers.
Synthetic calibrated records only; no production DB, actual match or video claim.
Authentication is seeded in a test-only session endpoint, not the login system.
"""
import json
import unittest
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from db import Base,get_db
from models import User,Club,Team,Player,Match,Event,EventContext,EventPosition,AutonomousAnalysis
from analysis_product_routes import save_collective_review
from analysis_result_clean_v2 import clean_analysis_result,download_analysis_report
from services.analysis_product import analysis_snapshot
from services.collective_review import context
from services.shot_context_review import source_key

class CalibratedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([User(id=1,email='owner@example.invalid',password_hash='synthetic'),User(id=2,email='other@example.invalid',password_hash='synthetic')])
            db.add(Club(id=1,name='QA only',owner_id=1))
            db.add(Team(id=1,club_id=1,owner_id=1,name='QA team',category='Women'))
            db.add_all([Player(id=2,team_id=1,name='QA 2',cap_number=2),Player(id=3,team_id=1,name='QA 3',cap_number=3)])
            db.add(Match(id=10,owner_id=1,team_id=1,opponent='QA opponent',competition='Synthetic records only',video_source='upload',video_path='qa-primary.mp4'))
            db.flush()
            db.add_all([Event(id=11,match_id=10,player_id=2,event_type='shot_on_target',second=.6,source='manual',confidence='CONFIRMED'),Event(id=12,match_id=10,event_type='save',second=.7,source='manual',confidence='CONFIRMED')])
            db.flush()
            db.add_all([EventContext(event_id=11,perspective='for'),EventContext(event_id=12,perspective='against'),EventPosition(event_id=11,period=1,segment_second=.6,x_pct=60,y_pct=50,provenance='manual_verified'),EventPosition(event_id=12,period=1,segment_second=.7,x_pct=96,y_pct=50,provenance='manual_verified')])
            def reviewed(side,cap,colour):
                return dict(side=side,cap_number=cap,colour=colour,provenance='coach_review',evidence='Synthetic reviewed identity')
            identities={};tracks=[]
            for i,(side,cap,x,y,colour) in enumerate([('for',2,14,0,'white'),('for',3,20,-2,'white'),('against',4,22,0,'blue'),('against',1,24,0,'red')],1):
                identities[str(i)]=reviewed(side,cap,colour)
                tracks.append(dict(id=i,colour=colour,segments=[[dict(second=t,x_m=x,y_m=y+(.2*t if side=='against' else 0)) for t in (0,.2,.4,.6,.8,1.,1.2)]],distance_m=.24 if side=='against' else 0))
            for tr in tracks:
                tr['forward_from_s']=0
                tr['raw_segments']=[[dict(p) for p in seg] for seg in tr['segments']]
            summary=dict(metric_field_map=dict(reference_second=0,status='estimated',goal_relative=True,revision='qa-cal-1',length_m=25,width_m=20,calibration_provenance='manual_reviewed_anchors',source_key=source_key('qa-primary.mp4'),tracks=tracks,shots=[dict(second=.6,x_m=15,y_m=0,provenance='manual_review_candidate',range_m=10)]),identity_reviews=dict(tracks=identities,events={'12':reviewed('against',1,'red')},shots={'0':reviewed('for',2,'white')}))
            db.add(AutonomousAnalysis(id=3,match_id=10,summary_json=json.dumps(summary)))
            db.commit()
        self.app=FastAPI()
        self.app.add_middleware(SessionMiddleware,secret_key='test-only-not-production')
        def database():
            with Session(self.engine) as db:yield db
        self.app.dependency_overrides[get_db]=database
        @self.app.get('/__qa_session/{uid}')
        def login(uid:int,request:Request):
            request.session['user_id']=uid
            return {'ok':True}
        self.app.add_api_route('/matches/{match_id}/analysis/collective-review',save_collective_review,methods=['POST'])
        self.app.add_api_route('/matches/{match_id}/analysis/result',clean_analysis_result,methods=['GET'])
        self.app.add_api_route('/matches/{match_id}/analysis/report.html',download_analysis_report,methods=['GET'])
        self.client=TestClient(self.app)
        self.client.get('/__qa_session/1')
        self.url='/matches/10/analysis/collective-review'
        self.report='/matches/10/analysis/result'
        self.export='/matches/10/analysis/report.html'
    def tearDown(self):
        self.client.close();self.engine.dispose()
    def snapshot(self):
        with Session(self.engine) as db:return analysis_snapshot(db,db.get(Match,10))
    def post(self,action,**data):
        ctx=context(self.snapshot());self.assertIsNotNone(ctx)
        return self.client.post(self.url,data=dict(binding=json.dumps(ctx),action=action,**data),follow_redirects=False)
    def shot(self):
        return self.post('add_shot',shot_index=0,event_id=11,save_event_id='12',goal_x=25,goal_width_m='3',defenders=['against:4','against:1'],keeper='against:1',assumed_lateral_span_m='1',evidence='Synthetic linked shot and save',shot_link_reviewed='true',roster_reviewed='true')
    def simulate(self):
        return self.post('add_3d',event_id=11,release_height_m=1.,defender_height_m=.8,radius_m=.35,horizontal_speed_mps=12.,sigma_m=.1,receivers=['for:3'],receiver_height_m=1.,reception_s='.2',budget_s='3',hypotheses_reviewed='true',motion_mode='predecision_velocity',evidence='Synthetic dynamic assumptions')
    def test_owner_lifecycle(self):
        self.assertEqual(self.snapshot()['advanced_motion']['status'],'experimental_partial')
        r=self.post('add',start_s=0,end_s=.6,period=1,attacking_side='for',attackers=['for:2','for:3'],defenders=['against:4','against:1'],carrier='for:2',goal_x=25,control_reviewed='true',roster_reviewed='true',center='for:3',marker='against:4',keeper='against:1',goal_width_m='3',evidence='Synthetic reviewed possession')
        self.assertEqual(r.status_code,303,r.text)
        r=self.post('add_recovery',before_s=.2,after_s=.4,start_s=.4,end_s=.8,period=1,losing_side='for',goal_x=0,defenders=['for:2','for:3'],unique_change_reviewed='true',continuous_play_reviewed='true',roster_reviewed='true',field_players_only='true',evidence='Synthetic reviewed transition')
        self.assertEqual(r.status_code,303,r.text)
        r=self.shot();self.assertEqual(r.status_code,303,r.text)
        r=self.simulate();self.assertEqual(r.status_code,303,r.text)
        s=self.snapshot()
        self.assertEqual(s['collective_review']['status'],'experimental_partial')
        self.assertEqual(s['recovery_review']['status'],'experimental_partial')
        self.assertEqual(s['shot_context']['rows'][0]['save']['id'],12)
        self.assertEqual(s['spatial_3d']['rows'][0]['motion_mode'],'predecision_velocity')
        for path in (self.report,self.export):
            r=self.client.get(path);self.assertEqual(r.status_code,200,r.text[:500])
            for marker in ('id="collectiveReview"','id="recoveryReview"','id="shotContext"','id="spatial3d"','Déplacements défensifs avant le tir','Synthetic dynamic assumptions'):self.assertIn(marker,r.text)
        r=self.post('clear_3d');self.assertEqual(r.status_code,303,r.text)
        s=self.snapshot();self.assertFalse(s['spatial_3d']['rows']);self.assertTrue(s['shot_context']['rows']);self.assertTrue(s['collective_review']['reports'])
    def test_owner_scope_and_stale_binding(self):
        r=self.shot();self.assertEqual(r.status_code,303,r.text)
        old=context(self.snapshot());other=TestClient(self.app)
        try:
            self.assertEqual(other.get(self.report).status_code,401)
            other.get('/__qa_session/2')
            self.assertEqual(other.get(self.report).status_code,404)
            self.assertEqual(other.get(self.export).status_code,404)
            self.assertEqual(other.post(self.url,data=dict(action='clear_shot',binding=json.dumps(old))).status_code,404)
            self.assertTrue(self.snapshot()['shot_context']['rows'])
        finally:other.close()
        with Session(self.engine) as db:
            auto=db.get(AutonomousAnalysis,3);s=json.loads(auto.summary_json);s['metric_field_map']['revision']='qa-cal-2';auto.summary_json=json.dumps(s);db.commit()
        r=self.client.post(self.url,data=dict(action='clear_shot',binding=json.dumps(old)));self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.snapshot()['shot_context']['rows'],[])
if __name__=='__main__':unittest.main()
