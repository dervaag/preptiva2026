"""Structural checks, not human/psychometric validation of the draft rubric."""
import copy
import unittest
from unittest.mock import patch


class JobRubricTests(unittest.TestCase):
    def test_opt_in_scope_hash_and_historical_compatibility(self):
        from app.ai.assessment import snapshot
        from app.ai.job_rubric import snapshot_hash
        legacy=snapshot('manager')
        self.assertEqual(legacy['version'],'2026-11-05.2')
        self.assertNotIn('profile_id',legacy)
        self.assertEqual(snapshot('manager',job_role='Engineering Manager'),legacy)
        draft=snapshot('manager',job_role=' ENGINEERING   MANAGER ',use_job_rubric=True)
        self.assertEqual(draft['sha256'],snapshot_hash(draft))
        self.assertFalse(draft['validated']);self.assertFalse(draft['job_reviewed_by_human'])
        self.assertEqual(sum(draft['weights'].values()),100)
        self.assertEqual(len(draft['weights']),5)
        for role,personas,job in [('hr',['hr'],'Engineering Manager'),('manager',['manager','user'],'Engineering Manager'),('manager',['manager'],'Product Manager')]:
            with self.assertRaises(ValueError):snapshot(role,personas,job_role=job,use_job_rubric=True)
        changed=copy.deepcopy(draft);changed['weights']['technical']+=1
        self.assertNotEqual(snapshot_hash(changed),draft['sha256'])
        changed=copy.deepcopy(draft);changed['sources'][0]['locator']='changed source'
        self.assertNotEqual(snapshot_hash(changed),draft['sha256'])

    def test_five_question_blueprint_covers_all_specialized_competencies(self):
        from app.ai.job_rubric import snapshot_profile
        from app.ai.blueprint import blueprint
        from app.ai.guidebook import snapshot
        assessment=snapshot_profile()
        for count in (3,5,7):
            plan=blueprint(count,'fixture-seed',['manager'],snapshot(),assessment)
            self.assertEqual(len(plan),count)
            self.assertTrue(all(set(p['competencies'])<=set(assessment['weights']) for p in plan))
            if count>=5:self.assertEqual({key for p in plan for key in p['competencies']},set(assessment['weights']))
        self.assertEqual(plan,blueprint(7,'fixture-seed',['manager'],snapshot(),assessment))

    def test_verifier_rejects_fabricated_cross_level_or_cross_competency_indicators(self):
        from app.ai.job_rubric import snapshot_profile
        from app.ai.scoring import verified_scores,aggregate
        assessment=snapshot_profile();quote='Saya membandingkan risiko dua pilihan dan menetapkan waktu untuk meninjau hasilnya.'
        value={'score':4,'evidence':[quote],'evidence_sufficiency':'sufficient','indicators_met':['em.problem_solving.l4'],
            'indicator_evidence':[{'indicator_id':'em.problem_solving.l4','turn_id':'q7','quote':quote}],
            'next_level_gap':'Hasil peninjauan belum dijelaskan.',
            'sources':[{'url':'https://invented.example','source_locator':'invented'}]}
        def verify(item):return verified_scores({'problem_solving':item},quote,['problem_solving'],[{'turn_id':'q7','transcript':quote}],assessment=assessment)['problem_solving']
        good=verify(value)
        self.assertEqual(good['status'],'measured');self.assertEqual(good['score'],4)
        self.assertEqual(good['next_level_indicators'][0]['level'],5)
        self.assertEqual(good['indicator_evidence'][0]['start'],0)
        self.assertTrue(all(s['url']!='https://invented.example' for s in good['sources']))
        self.assertTrue(all(s['origin']=='internal' for s in good['sources']))
        for changes in ({'indicators_met':['em.problem_solving.l5']},{'indicators_met':['em.technical.l4']},
                        {'indicators_met':['made-up']},{'indicator_evidence':[]},{'score':4.5},{'score':True},{'score':'4'},
                        {'score':6,'indicators_met':['em.problem_solving.l5'],'indicator_evidence':[{'indicator_id':'em.problem_solving.l5','quote':quote}]},
                        {'indicator_evidence':[{'indicator_id':'em.problem_solving.l4','quote':'Fabricated original quotation.'}]},
                        {'indicator_evidence':[{'indicator_id':'em.problem_solving.l4','quote':quote,'turn_id':'q8'}]}):
            with self.subTest(changes=changes):
                bad=verify({**value,**changes})
                self.assertEqual(bad['status'],'insufficient')
                total,_=aggregate([{'problem_solving':bad}],assessment['weights'],assessment)
                self.assertIsNone(total)
        missing_sufficiency=dict(value);missing_sufficiency.pop('evidence_sufficiency')
        self.assertEqual(verify(missing_sufficiency)['status'],'insufficient')
        highest=verify({**value,'score':5,'indicators_met':['em.problem_solving.l5'],
            'indicator_evidence':[{'indicator_id':'em.problem_solving.l5','quote':quote}]})
        self.assertEqual(highest['next_level_gap'],'');self.assertEqual(highest['next_level_indicators'],[])

    def test_general_scoring_does_not_require_em_indicators(self):
        from app.ai.assessment import snapshot
        from app.ai.scoring import verified_scores
        quote='Saya mengukur hasil eksperimen bersama tim.'
        scores=verified_scores({'communication':{'score':4,'evidence':[quote]}},quote,['communication'],assessment=snapshot('hr'))
        self.assertEqual(scores['communication']['status'],'measured')
        self.assertNotIn('indicators_met',scores['communication'])


class RubricOutputRepairTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_indicator_fields_are_repaired_and_persistent_invalid_output_fails(self):
        from unittest.mock import AsyncMock
        from app.ai import orchestrator
        from app.ai.job_rubric import snapshot_profile,evaluation_fields
        assessment=snapshot_profile();quote='Saya membandingkan risiko alternatif bersama tim.'
        context={**evaluation_fields(assessment,['technical']),'interviewer':'manager','language':'id','competencies':['technical'],
            'source_turns':[{'turn_id':'q1','transcript':quote}],'question':'Bagaimana Anda membandingkan pendekatan teknis?','transcript':quote,'rubric':assessment['rubric']}
        incomplete={'competency_scores':{'technical':{'score':4,'evidence':[quote]}}}
        valid={'competency_scores':{'technical':{'score':4,'evidence':[quote],'evidence_sufficiency':'sufficient','rationale':'Synthetic contract test.',
            'indicators_met':['em.technical.l4'],'indicator_evidence':[{'indicator_id':'em.technical.l4','turn_id':'q1','quote':quote}],
            'next_level_gap':'Hasil peninjauan belum dijelaskan.'}}}
        with patch('app.ai.orchestrator.complete',AsyncMock(side_effect=[incomplete,valid])) as complete:
            self.assertEqual(await orchestrator.evaluate(context),valid)
            self.assertEqual(complete.await_count,2)
            self.assertIn('repair_required',complete.call_args.args[1])
        with patch('app.ai.orchestrator.complete',AsyncMock(return_value=incomplete)) as complete:
            with self.assertRaises(ValueError):await orchestrator.evaluate(context)
            self.assertEqual(complete.await_count,2)
