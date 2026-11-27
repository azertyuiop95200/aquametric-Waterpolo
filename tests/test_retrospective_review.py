import unittest
from test_pass_review import sample
from test_review_reference_import import read
from services.review_reference_import import summarize
from jinja2 import Environment, FileSystemLoader

def make(**kw):
    p=sample();r=p['reference']['pass_review']['actions'][0]
    r.update(outcome='unknown',direct_sequence=None,related_event_id=None,event_relation=None)
    follow=dict(next_frame=40,next_team='bleus',next_kind='carry',path_consistent=True,distinct_receiver=True,intervening_control='not_observed',intervening_restart='not_observed',reason='Continuité plausible',alternative='Reprise masquée possible',evidence=['preuves/fixture.jpg'])
    follow.update(kw);r['retrospective']=follow;return p
def run(p):return summarize(read(p)[0],'bleus')['pass_review']

class RetrospectiveTests(unittest.TestCase):
    def test_probable_is_not_confirmed(self):
        p=run(make());d=p['actions'][0]['retrospective_decision']
        self.assertEqual(d['status'],'probable_retained');self.assertEqual(d['pass_decision'],'probable_completed')
        self.assertFalse(d['confirmed']);self.assertEqual(p['teams']['bleus']['completed'],0)
        self.assertEqual(p['teams']['bleus']['unknown_outcomes'],1);self.assertEqual(p['retrospective_summary']['without_tactical_decision'],0)
    def test_same_team_only(self):
        p=run(make(distinct_receiver=None));self.assertEqual(p['actions'][0]['retrospective_decision']['pass_decision'],'undetermined')
    def test_unseen_path(self):
        p=run(make(path_consistent=None));self.assertEqual(p['actions'][0]['retrospective_decision']['status'],'later_control_only')
    def test_restart(self):
        self.assertEqual(run(make(intervening_restart='observed'))['actions'][0]['retrospective_decision']['status'],'continuity_not_supported')
    def test_opponent(self):
        p=make();p['reference']['possession_review_intervals'][0].update(start_s=1.1,end_s=1.5,before_team='blancs',after_team='bleus')
        d=run(p)['actions'][0]['retrospective_decision'];self.assertEqual(d['status'],'continuity_not_supported');self.assertEqual(d['conflict_ids'],['P1'])
    def test_opponent_after_horizon(self):
        self.assertEqual(run(make())['actions'][0]['retrospective_decision']['conflict_ids'],[])
    def test_changed(self):
        p=make(next_team='blancs');p['reference']['pass_review']['actions'][0]['control_team']='blancs'
        d=run(p)['actions'][0]['retrospective_decision'];self.assertEqual(d['status'],'probable_changed');self.assertEqual(d['pass_decision'],'undetermined')
    def test_arrival(self):
        p=make();a=p['reference']['pass_review']['actions'][0]
        a.update(state='arrival_only',team=None,arrival_first_frame=22,release_last_held_frame=None,release_first_free_frame=None,sender_role='unknown',distinct_receiver=None)
        s=run(p);self.assertEqual(s['actions'][0]['retrospective_decision']['status'],'later_control_only')
        self.assertEqual(s['retrospective_summary']['arrival_contexts'],1);self.assertEqual(s['teams']['bleus']['observed_attempts'],0)
    def test_wrong_team(self):
        with self.assertRaises(ValueError):read(make(next_team='blancs'))
    def test_wrong_frame(self):
        for frame in [31,48,True]:
            with self.assertRaises(ValueError):read(make(next_frame=frame))
    def test_evidence(self):
        with self.assertRaises(ValueError):read(make(evidence=['preuves/nonexistent.jpg']))
    def test_alternative(self):
        with self.assertRaises(ValueError):read(make(alternative=''))
    def test_confirmed_unchanged(self):
        p=make();p['reference']['pass_review']['actions'][0].update(outcome='completed',direct_sequence=True)
        with self.assertRaises(ValueError):read(p)
    def test_link_valid(self):
        p=make(next_kind='pass',next_frame=40,next_pass_id='PA2')
        a=p['reference']['pass_review']['actions'][0]
        b=dict(a,id='PA2',release_last_held_frame=39,release_first_free_frame=40,contact_frame=43,control_frame=44,outcome='completed',direct_sequence=True)
        b.pop('retrospective');p['reference']['pass_review']['actions'].append(b)
        self.assertEqual(run(p)['actions'][0]['retrospective_decision']['next_pass_id'],'PA2')
        a['retrospective']['next_frame']=41
        with self.assertRaises(ValueError):read(p)
    def test_template(self):
        p=run(make());env=Environment(loader=FileSystemLoader('source/templates'))
        h=env.get_template('pass_review_report.html').render(p={'pass_review':p,'home_color':'bleus'},ref={'period':1})
        self.assertIn('Conservation probable',h);self.assertIn('réception partenaire probable',h);self.assertIn('Alternative',h)
