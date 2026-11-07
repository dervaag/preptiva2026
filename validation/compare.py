"""Descriptive comparison of supplied human decisions and independent AI runs.

Missing evidence stays unscored. Every report keeps validated=false.
"""
import argparse
import itertools
import json
from pathlib import Path
from statistics import mean
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))


def kappa(a,b):
    if len(a)!=len(b) or not a:
        raise ValueError('Rating vectors must have equal nonzero length.')
    observed=mean((x-y)**2 for x,y in zip(a,b))
    expected=mean((x-y)**2 for x in a for y in b)
    return None if expected==0 else round(1-observed/expected,4)


def valid_score(value):
    return type(value) is int and value in range(1,6)


def metrics(cases):
    if not cases:
        return {'n':0,'ai_vs_consensus_kappa':None,'mean_absolute_error':None,'within_one_point_percent':None}
    consensus=[c['consensus_score'] for c in cases];first=[c['ai_runs'][0] for c in cases]
    return {'n':len(cases),'ai_vs_consensus_kappa':kappa(first,consensus),
        'mean_absolute_error':round(mean(abs(a-b) for a,b in zip(first,consensus)),4),
        'within_one_point_percent':round(100*mean(abs(a-b)<=1 for a,b in zip(first,consensus)),2)}


def compare(dataset):
    all_cases=dataset.get('cases',[])
    if len(all_cases)<2:
        raise ValueError('Provide at least two cases; a small sample is not validation.')
    ids=[c['id'] for c in all_cases]
    if len(set(ids))!=len(ids):
        raise ValueError('Duplicate case IDs.')
    if any(c.get('split') not in ('test','calibration') for c in all_cases):
        raise ValueError('Each case must have an explicit test/calibration split.')
    calibration=[c['id'] for c in all_cases if c['split']=='calibration']
    cases=[c for c in all_cases if c['split']=='test']
    if len(cases)<2:
        raise ValueError('Provide at least two held-out test cases; calibration is excluded.')
    raters=sorted(cases[0].get('human_ratings',{}))
    if len(raters)<3:
        raise ValueError('Diperlukan penilaian independen minimal tiga asesor manusia pada setiap kasus uji.')
    if dataset.get('schema_version')==2:
        from validation.kit import digest,independent_hash,validate_rating
        digest(dataset)
        audit=dataset.get('consensus_audit',{})
        if audit.get('reviewed_independent_ratings') is not True or audit.get('independent_ratings_hash')!=independent_hash(dataset):
            raise ValueError('Dataset profil memerlukan konsensus terverifikasi melalui perintah consensus.')
    comparable=[];excluded=[];ai_complete=[]
    for case in cases:
        if sorted(case.get('human_ratings',{})) != raters:
            raise ValueError('Each test case must be rated independently by the same assessors.')
        values=list(case['human_ratings'].values())+[case.get('consensus_score')]+case.get('ai_runs',[])
        if any(v is not None and not valid_score(v) for v in values):
            raise ValueError('Scores must be integer 1–5 or null when evidence is insufficient.')
        if len(case.get('ai_runs',[]))<5:
            raise ValueError('Provide at least five independent AI runs per test case.')
        if not case.get('transcript') or not case.get('competency') or not isinstance(case.get('ai_quotes'),list):
            raise ValueError('Every test case needs original transcript, competency, and ai_quotes list.')
        if dataset.get('schema_version')==2:
            validate_rating(dataset,case,{**case.get('consensus_evidence',{}),'score':case.get('consensus_score')})
            if len(case.get('ai_statuses',[]))!=len(case['ai_runs']):
                raise ValueError('Each AI run in a profile dataset needs its evidence status.')
            for score,status in zip(case['ai_runs'],case['ai_statuses']):
                if (score is not None)!=(status=='measured') or status not in ('measured','insufficient','unusable_transcript','not_assessed'):
                    raise ValueError('AI score/status mismatch.')
        reasons=[]
        if any(v is None for v in case['human_ratings'].values()): reasons.append('independent_human_evidence_insufficient')
        if case.get('consensus_score') is None: reasons.append('consensus_evidence_insufficient')
        if any(v is None for v in case['ai_runs']): reasons.append('ai_evidence_insufficient')
        else: ai_complete.append(case)
        if reasons: excluded.append({'case_id':case['id'],'competency':case['competency'],'reasons':reasons})
        else: comparable.append(case)
    pairs=[]
    for a,b in itertools.combinations(raters,2):
        pair_cases=[c for c in cases if c['human_ratings'][a] is not None and c['human_ratings'][b] is not None]
        pairs.append({'raters':[a,b],'n':len(pair_cases),'quadratic_weighted_kappa':kappa(
            [c['human_ratings'][a] for c in pair_cases],[c['human_ratings'][b] for c in pair_cases]) if pair_cases else None})
    quotes=[(q,c['transcript']) for c in cases for q in c['ai_quotes']]
    valid_quotes=sum(isinstance(q,str) and len(q.strip())>=8 and q in transcript for q,transcript in quotes)
    overall=metrics(comparable)
    groups={language:metrics([c for c in comparable if c.get('language','unknown')==language]) for language in sorted({c.get('language','unknown') for c in cases})}
    competencies={key:metrics([c for c in comparable if c['competency']==key]) for key in sorted({c['competency'] for c in cases})}
    for key,group in competencies.items():
        group['n_test']=sum(c['competency']==key for c in cases)
    return {'validated':False,'purpose':'descriptive assessor comparison; no automatic selection-validity claim',
        'rubric_version':dataset.get('rubric_version'),'rubric_sha256':dataset.get('rubric_sha256'),
        'model':dataset.get('model'),'ai_provenance':dataset.get('ai_provenance'),
        **overall,'n_total':len(all_cases),'n_test':len(cases),'n_comparable':len(comparable),
        'excluded_calibration_ids':calibration,'excluded_cases':excluded,
        'comparison_policy':'Complete cases only: all independent raters, consensus and all AI runs must be measured. Exclusions may bias estimates; inspect them before interpretation.',
        'human_pairs':pairs,'stability_n':len(ai_complete),
        'stable_range_at_most_one_percent':round(100*mean(max(c['ai_runs'])-min(c['ai_runs'])<=1 for c in ai_complete),2) if ai_complete else None,
        'verbatim_quote_percent':round(100*valid_quotes/len(quotes),2) if quotes else None,
        'quote_count':len(quotes),'language_groups':groups,'competency_groups':competencies,
        'pending_human_review':['assessor qualifications and independence','quote relevance to indicator','job relevance','sample coverage','fairness and STT sensitivity']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:
        report=compare(json.loads(args.dataset.read_text()))
        from validation.kit import write_private
        write_private(args.output,json.dumps(report,indent=2)+'\n')
    except (ValueError,KeyError,TypeError,FileExistsError) as exc:
        parser.error(str(exc))
    print(f'Report saved: {args.output}; validated remains false.')

if __name__=='__main__':main()
