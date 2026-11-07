"""Synthetic workflow fixtures; none of these values are human assessments."""
import copy
import json
import re
import unittest
from validation.kit import (starter, packet, digest, merge, consensus_template,
    apply_consensus, independent_hash, validate_rating)
from validation.compare import compare


class AssessorWorkflowTests(unittest.TestCase):
    def dataset(self):
        data=starter('engineering-manager')
        data['cases']=[data['cases'][1],data['cases'][2],data['cases'][0]]
        return data

    def rating(self, data, rater='assessor-a', score=3):
        rows=[]
        for case in data['cases']:
            indicator=data['assessment']['competency_definitions'][case['competency']]['levels'][str(score)]['id']
            rows.append({'case_id':case['id'],'status':'measured','score':score,
                'quote':case['transcript'],'rationale':'Automated workflow fixture, not an actual human assessment.',
                'indicators_met':[indicator],'next_level_gap':'Automated test only; not a substantive assessment.' if score<5 else ''})
        return {'assessor_id':rater,'dataset_hash':digest(data),'personally_rated_independently':True,'ratings':rows}

    def rated(self,data):
        return merge(data,[self.rating(data,name) for name in ('assessor-a','assessor-b','assessor-c')])

    def consensus(self,data):
        template=consensus_template(data)
        template.update(coordinator_id='coordinator-test',reviewed_independent_ratings=True)
        template['decisions']=self.rating(data)['ratings']
        return apply_consensus(data,template)

    def test_profile_starter_is_draft_unrated_and_split_before_scoring(self):
        data=starter('engineering-manager')
        self.assertEqual(len(data['cases']),20)
        self.assertEqual(sum(c['split']=='calibration' for c in data['cases']),5)
        self.assertEqual(sum(c['split']=='test' for c in data['cases']),15)
        self.assertEqual(len({c['competency'] for c in data['cases']}),5)
        self.assertFalse(data['validated']);self.assertFalse(data['job_reviewed_by_human'])
        self.assertTrue(all(not c['human_ratings'] and not c['ai_runs'] and c['consensus_score'] is None for c in data['cases']))
        self.assertEqual(data['assessment']['status'],'draft_pending_expert_review')

    def test_blind_packet_excludes_scores_and_preserves_script_like_transcript(self):
        data=self.dataset();case=data['cases'][0]
        case.update(human_ratings={'private-assessor':1},consensus_score=2,ai_runs=[5]*5)
        case['transcript']+=' </script><script>window.bad=true</script>'
        output=packet(data,'assessor-a')
        raw=output.split('<script type="application/json" id="packet">')[1].split('</script>')[0]
        visible=json.loads(raw)
        self.assertEqual(visible['cases'][0]['transcript'],case['transcript'])
        self.assertNotIn('private-assessor',output)
        self.assertNotIn('ai_runs',raw);self.assertNotIn('human_ratings',raw);self.assertNotIn('consensus_score',raw)
        self.assertNotIn('</script><script>window.bad=true',raw)
        self.assertNotIn('split',visible['cases'][0])
        self.assertNotRegex(output,r'id="independent"[^>]*checked')

    def test_profile_hash_binds_split_context_and_rubric_snapshot(self):
        data=self.dataset();rating=self.rating(data)
        changed=copy.deepcopy(data);changed['cases'][0]['split']='calibration'
        self.assertNotEqual(digest(data),digest(changed))
        with self.assertRaises(ValueError):merge(changed,[rating])
        changed=copy.deepcopy(data);changed['assessment']['weights']['technical']+=1
        with self.assertRaises(ValueError):digest(changed)
        changed=copy.deepcopy(data);changed['job_role']='Sales Manager'
        with self.assertRaises(ValueError):digest(changed)

    def test_merge_rejects_other_competency_level_and_fabricated_quote(self):
        data=self.dataset();good=self.rating(data)
        for change in ({'indicators_met':['em.technical.l3']},
                       {'indicators_met':['em.problem_solving.l4']},
                       {'quote':'This quotation does not exist in the transcript.'},
                       {'next_level_gap':''}):
            bad=copy.deepcopy(good);bad['ratings'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):merge(data,[bad])
        complete=merge(data,[good])
        with self.assertRaises(ValueError):merge(complete,[good])
        bad=copy.deepcopy(good);bad['personally_rated_independently']=False
        with self.assertRaises(ValueError):merge(data,[bad])

    def test_insufficient_is_unscored_and_does_not_claim_indicator(self):
        data=self.dataset();rating=self.rating(data)
        row=rating['ratings'][0]
        row.update(status='insufficient',score=None,quote='',indicators_met=[],next_level_gap='')
        result=merge(data,[rating])
        self.assertIsNone(result['cases'][0]['human_ratings']['assessor-a'])
        row['indicators_met']=['em.problem_solving.l3']
        with self.assertRaises(ValueError):merge(data,[rating])

    def test_consensus_requires_three_raters_and_cannot_auto_fill_or_overwrite(self):
        data=self.dataset()
        with self.assertRaises(ValueError):consensus_template(data)
        two=merge(data,[self.rating(data,name) for name in ('assessor-a','assessor-b')])
        with self.assertRaises(ValueError):consensus_template(two)
        rated=self.rated(data);template=consensus_template(rated)
        self.assertFalse(template['reviewed_independent_ratings'])
        self.assertTrue(all(c['score'] is None and not c['status'] for c in template['decisions']))
        with self.assertRaises(ValueError):apply_consensus(rated,template)
        result=self.consensus(rated)
        self.assertEqual(independent_hash(result),independent_hash(rated))
        self.assertFalse(result['validated'])
        with self.assertRaises(ValueError):self.consensus(result)
        template.update(coordinator_id='coordinator-test',reviewed_independent_ratings=True,
            decisions=self.rating(data)['ratings'])
        changed=copy.deepcopy(rated);changed['cases'][0]['human_evidence']['assessor-a']['rationale']+=' Changed.'
        with self.assertRaises(ValueError):apply_consensus(changed,template)

    def test_compare_reports_null_exclusions_and_denominators_without_inventing_scores(self):
        data=self.dataset();rated=self.rated(data)
        # Deliberate insufficient evidence in one independently rated test case.
        case=rated['cases'][1];case['human_ratings']['assessor-c']=None
        case['human_evidence']['assessor-c'].update(status='insufficient',quote='',indicators_met=[],next_level_gap='')
        decision=consensus_template(rated)
        decision.update(coordinator_id='coordinator-test',reviewed_independent_ratings=True,
            decisions=self.rating(data)['ratings'])
        decision['decisions'][1].update(status='insufficient',score=None,quote='',indicators_met=[],next_level_gap='')
        agreed=apply_consensus(rated,decision)
        for case in agreed['cases']:
            if case['split']=='test':
                case.update(ai_runs=[3]*5,ai_statuses=['measured']*5,ai_quotes=[case['transcript']])
        agreed['cases'][1]['ai_runs'][0]=None;agreed['cases'][1]['ai_statuses'][0]='insufficient'
        report=compare(agreed)
        self.assertEqual(report['n_total'],3);self.assertEqual(report['n_test'],2)
        self.assertEqual(report['n_comparable'],1);self.assertEqual(report['stability_n'],1)
        self.assertEqual(report['excluded_calibration_ids'],[agreed['cases'][2]['id']])
        self.assertEqual(len(report['excluded_cases'][0]['reasons']),3)
        self.assertEqual(report['within_one_point_percent'],100)
        self.assertFalse(report['validated'])
        self.assertEqual(report['competency_groups']['problem_solving']['n_test'],2)
        agreed['cases'][0]['ai_runs']=[None]*5;agreed['cases'][0]['ai_statuses']=['insufficient']*5
        empty=compare(agreed)
        self.assertEqual(empty['n_comparable'],0);self.assertIsNone(empty['ai_vs_consensus_kappa'])
        self.assertIsNone(empty['within_one_point_percent']);self.assertIsNone(empty['stable_range_at_most_one_percent'])

    def test_compare_requires_completed_consensus_and_five_runs(self):
        data=self.rated(self.dataset())
        for case in data['cases']:
            case.update(ai_runs=[3]*5,ai_statuses=['measured']*5)
        with self.assertRaises(ValueError):compare(data)
        agreed=self.consensus(data)
        agreed['cases'][0]['ai_runs']=[3]*4;agreed['cases'][0]['ai_statuses']=['measured']*4
        with self.assertRaises(ValueError):compare(agreed)

    def test_legacy_general_packets_remain_usable(self):
        data=starter()
        self.assertEqual(len(data['cases']),7)
        row={'assessor_id':'assessor-a','dataset_hash':digest(data),'personally_rated_independently':True,
             'ratings':[{'case_id':c['id'],'status':'measured','score':3,'quote':c['transcript'],
                        'rationale':'Synthetic test fixture only.'} for c in data['cases']]}
        result=merge(data,[row])
        self.assertEqual(result['cases'][0]['human_ratings']['assessor-a'],3)
        self.assertFalse(result['validated'])

if __name__=='__main__':unittest.main()
