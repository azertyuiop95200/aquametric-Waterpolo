"""Create a visual showcase account and synthetic match for UI demonstrations.

Run with a separate DATABASE_URL. The synthetic match is explicitly labelled as
showcase data and must not be confused with an official match analysis.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from sqlalchemy import select

from db import Base, engine, SessionLocal
from auth import hash_password
from models import (User, Club, Team, Player, Match, Event, EventContext, VisionAnalysis, VisionSample,
                    AutonomousAnalysis, AutonomousEventCandidate, OfficialDataSource, OfficialFixture, OfficialStanding)
from main import UPLOAD_DIR

Base.metadata.create_all(engine)


def make_video(path: Path):
    if path.exists():
        return
    fps=10; w,h=960,540; seconds=24
    wr=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    for i in range(seconds*fps):
        t=i/fps
        frame=np.full((h,w,3),(182,130,37),dtype=np.uint8)
        cv2.rectangle(frame,(0,0),(665,96),(16,20,23),-1)
        home = 7 if t<11 else 8 if t<19 else 9
        away = 7 if t<20 else 8
        clock=max(0,310-int(t)); mm,ss=divmod(clock,60)
        cv2.putText(frame,f'ESP {home:02d}  GRE {away:02d}  Q4  {mm:02d}:{ss:02d}',(17,66),cv2.FONT_HERSHEY_SIMPLEX,1.45,(255,255,255),3,cv2.LINE_AA)
        # Simplified pool/player shapes for UI video preview.
        cv2.line(frame,(70,150),(890,150),(240,240,240),2); cv2.line(frame,(70,440),(890,440),(240,240,240),2)
        for j in range(6):
            x=150+j*115+int(12*np.sin(t+j)); y=250+(j%2)*95
            cv2.circle(frame,(x,y),18,(245,245,245),-1); cv2.circle(frame,(x,y-15),7,(235,235,235),-1)
        for j in range(6):
            x=175+j*112-int(10*np.sin(t+j)); y=300+(j%2)*90
            cv2.circle(frame,(x,y),18,(25,45,220),-1); cv2.circle(frame,(x,y-15),7,(25,45,220),-1)
        bx=420+int(95*np.sin(t*1.6)); by=245+int(35*np.cos(t*1.3)); cv2.circle(frame,(bx,by),7,(35,225,240),-1)
        wr.write(frame)
    wr.release()


def add_event(db, match, second, etype, perspective='for', phase='even_attack', player=None, note='Showcase evidence'):
    e=Event(match_id=match.id, player_id=player.id if player else None, second=second, event_type=etype,
            confidence='CONFIRMED', note=note, source='showcase_demo')
    db.add(e); db.flush(); db.add(EventContext(event_id=e.id,perspective=perspective,phase_tag=phase)); return e


def run():
    db=SessionLocal()
    try:
        user=db.scalar(select(User).where(User.email=='showcase@aquametric.local'))
        if user:
            print('Showcase already exists.'); return
        user=User(email='showcase@aquametric.local',password_hash=hash_password('demo12345'),name='Performance Staff',country='International')
        db.add(user); db.flush()
        club=Club(name='AquaMetric Showcase Club',country='International',division='High Performance Demo',category='Women',owner_id=user.id)
        db.add(club); db.flush()
        team=Team(name='Spain U20 — Showcase',club_id=club.id,owner_id=user.id,category='Women'); db.add(team); db.flush()
        players=[]
        for n,name,role in [(1,'Goalkeeper','Goalkeeper'),(2,'Perimeter A','Perimeter'),(4,'Defender A','Defender'),(6,'Centre A','Centre'),(8,'Left Side','Perimeter'),(10,'Right Side','Perimeter')]:
            p=Player(team_id=team.id,name=name,cap_number=n,primary_role=role);db.add(p);players.append(p)
        db.flush()
        video='showcase_waterpolo.mp4'; make_video(UPLOAD_DIR/video)
        match=Match(owner_id=user.id,team_id=team.id,opponent='Greece U20 — Showcase',competition='Women U20 — interface showcase',match_date='2025-08-16',video_source='upload',video_path=video,status='autonomy_scanned')
        db.add(match);db.flush()
        # Three power plays with different processes.
        seq=[
            (20,'power_play_start','for','power_play',None,'Exclusion creates 6v5'),(22,'pass_complete','for','power_play',players[1],''),(24,'pass_complete','for','power_play',players[4],''),(27,'pass_complete','for','power_play',players[5],''),(29,'goal','for','power_play',players[4],'Cross-cage finish'),
            (70,'power_play_start','for','power_play',None,''),(73,'pass_complete','for','power_play',players[4],''),(76,'pass_complete','for','power_play',players[1],''),(82,'shot_blocked','for','power_play',players[5],'Lane closed'),(84,'recovery','for','power_play',players[2],''),(88,'turnover','for','power_play',players[2],'Late possession loss'),
            (130,'power_play_start','for','power_play',None,''),(132,'pass_complete','for','power_play',players[1],''),(135,'pass_complete','for','power_play',players[4],''),(138,'goal','for','power_play',players[3],'Quick inside finish'),
            # Counterattack and defensive recovery.
            (175,'counterattack_start','for','counterattack',players[2],''),(178,'pass_complete','for','counterattack',players[1],''),(181,'goal','for','counterattack',players[4],'Transition finish'),
            (205,'defensive_recovery_start','for','defensive_recovery',players[5],''),(210,'fast_recovery','for','defensive_recovery',players[5],''),(213,'interception','for','defensive_recovery',players[2],''),
            (245,'defensive_recovery_start','for','defensive_recovery',players[4],''),(251,'late_recovery','for','defensive_recovery',players[4],''),(254,'goal','against','defensive_recovery',None,'Opponent scores before shape is restored'),
            # 5-on-6 defence.
            (285,'penalty_kill_start','against','penalty_kill',None,''),(288,'pass_complete','against','penalty_kill',None,''),(291,'shot_blocked','against','penalty_kill',None,''),(292,'block','for','penalty_kill',players[2],'Block closes lane'),
            (330,'penalty_kill_start','against','penalty_kill',None,''),(334,'pass_complete','against','penalty_kill',None,''),(337,'goal','against','penalty_kill',None,'Opponent converts'),
            # Even play and tagged score context.
            (370,'goal','for','even_attack',players[3],''),(410,'goal','against','even_defence',None,''),(450,'goal','for','even_attack',players[1],''),(490,'goal','against','even_defence',None,''),(530,'goal','for','even_attack',players[4],''),(570,'goal','against','even_defence',None,''),(610,'goal','for','even_attack',players[5],''),(650,'goal','against','even_defence',None,''),(690,'goal','for','even_attack',players[1],''),(730,'goal','against','even_defence',None,''),
            (760,'bad_pass','for','even_attack',players[4],'Pass into covered lane'),(775,'turnover','for','even_attack',players[1],'Ball lost under pressure'),(790,'block','for','even_defence',players[2],''),(805,'save','for','even_defence',players[0],''),(820,'interception','for','even_defence',players[5],''),
        ]
        for row in seq: add_event(db,match,*row)
        # Vision data for showcase charts.
        samples=[]
        for i in range(48):
            second=i*18.0; active=0.48+0.32*abs(np.sin(i*.52)); motion=0.25+0.28*abs(np.sin(i*.71)); scene=.08 if i%11 else .42
            samples.append({'second':second,'pool_ratio':.63,'motion_score':round(float(motion),3),'scene_change':scene,'active_score':round(float(active),3),'action_score':round(float(min(1,.45*motion+.4*active+.15*scene)),3)})
        va=VisionAnalysis(match_id=match.id,status='complete',engine_version='visual-baseline-v1',source_kind='upload',duration_seconds=870,fps=25,width=1920,height=1080,sample_interval_seconds=18,sample_count=len(samples),video_type='full_match_candidate',confidence='MODERATE',avg_pool_ratio=.63,avg_motion_score=.39,scene_cut_rate=.08,active_seconds_estimate=620,active_windows_json=json.dumps([{'start':18,'end':205,'duration':187,'confidence':.76},{'start':230,'end':440,'duration':210,'confidence':.72},{'start':470,'end':830,'duration':360,'confidence':.74}]),interesting_moments_json=json.dumps([{'second':130,'score':.84,'reason':'high visual activity candidate'},{'second':245,'score':.79,'reason':'high visual activity candidate'},{'second':690,'score':.88,'reason':'high visual activity candidate'}]),scoreboard_candidates_json=json.dumps([{'name':'top_wide','x':0,'y':0,'w':.72,'h':.2,'score':.83},{'name':'top_left','x':0,'y':0,'w':.42,'h':.2,'score':.68}]),contact_sheet_file='',limitations_json=json.dumps(['Showcase vision metrics are illustrative.']))
        db.add(va);db.flush()
        for x in samples: db.add(VisionSample(analysis_id=va.id,**x))
        observations=[{'second':0,'roi_name':'top_wide','raw_text':'ESP 03 GRE 07 Q2 00:20','normalized_text':'ESP 03 GRE 07 Q2 00:20','ocr_confidence':.91,'period':2,'clock_seconds':20,'numbers':[3,7],'home_score':3,'away_score':7},{'second':430,'roi_name':'top_wide','raw_text':'ESP 06 GRE 07 Q3 00:05','normalized_text':'ESP 06 GRE 07 Q3 00:05','ocr_confidence':.89,'period':3,'clock_seconds':5,'numbers':[6,7],'home_score':6,'away_score':7},{'second':690,'roi_name':'top_wide','raw_text':'ESP 09 GRE 08 Q4 02:05','normalized_text':'ESP 09 GRE 08 Q4 02:05','ocr_confidence':.92,'period':4,'clock_seconds':125,'numbers':[9,8],'home_score':9,'away_score':8}]
        aa=AutonomousAnalysis(match_id=match.id,status='complete',engine_version='autonomy-v0.1',ocr_available=True,observations_json=json.dumps(observations),periods_json=json.dumps([{'period':2,'start_second':0,'end_second':210,'confidence':'MODERATE','evidence_count':8},{'period':3,'start_second':225,'end_second':450,'confidence':'MODERATE','evidence_count':9},{'period':4,'start_second':465,'end_second':870,'confidence':'HIGH','evidence_count':13}]),summary_json=json.dumps({'scoreboard_observations':30,'periods_observed':3,'goal_candidates':6,'whistle_candidates':12,'action_candidates':18,'autonomy_level':'L1 — scoreboard + visual + audio evidence','audio_scan':'ready','scientific_honesty':'Candidates stay separate from verified truth.'}),limitations_json=json.dumps(['Player/ball identity model is not represented in this interface showcase.']))
        db.add(aa);db.flush()
        cand=[(126,'whistle_candidate',.76,'Whistle-like audio burst precedes numerical phase.'),(139,'goal_candidate_home',.86,'Scoreboard increase supports a goal candidate.'),(244,'whistle_candidate',.73,'Whistle-like burst near defensive transition.'),(690,'goal_candidate_home',.88,'Scoreboard increase and active-play peak align.'),(731,'goal_candidate_away',.82,'Opponent score change observed.')]
        for sec,typ,conf,text in cand: db.add(AutonomousEventCandidate(analysis_id=aa.id,match_id=match.id,second=sec,event_type=typ,confidence_score=conf,confidence_label='HIGH' if conf>=.88 else 'MODERATE',summary=text,evidence_json=json.dumps({'showcase':True}),source='showcase_demo'))
        # Minimal official data to make dashboard/calendar credible.
        src=db.scalar(select(OfficialDataSource).where(OfficialDataSource.name=='Showcase official feed'))
        if not src:
            src=OfficialDataSource(name='Showcase official feed',provider='Official demo feed',region='Europe',url='https://example.invalid',parser_kind='showcase',refresh_interval_hours=12,enabled=True,records_count=3)
            db.add(src);db.flush()
        db.add(OfficialFixture(source_id=src.id,external_key='show-1',competition='Women U20',season='2025',category='Women',start_text='2026-09-05 18:00',home_team='Spain U20',away_team='Italy U20',status='scheduled',venue='International'))
        for pos,name,pts in [(1,'Spain U20',12),(2,'USA U20',10),(3,'Greece U20',8),(4,'Italy U20',6)]: db.add(OfficialStanding(source_id=src.id,competition='Women U20 Showcase',season='2025',category='Women',position=pos,team_name=name,points=pts,played=4,won=max(0,5-pos),lost=max(0,pos-1),goals_for=50-pos*3,goals_against=28+pos*2,goal_diff=22-pos*5))
        db.commit();print(f'Showcase created: match {match.id}; login showcase@aquametric.local / demo12345')
    finally:
        db.close()

if __name__=='__main__': run()
