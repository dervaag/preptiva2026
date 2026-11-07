"""Opt-in synthetic rubric contract check with the configured LLM; never human validation."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


async def run():
    from app.ai import orchestrator,guidebook
    from app.ai.job_rubric import snapshot_profile,evaluation_fields
    from app.ai.scoring import verified_scores
    assessment=snapshot_profile()
    cv='Saya memimpin tim engineering layanan transaksi. Saya membandingkan risiko perubahan sistem, mengoordinasikan prioritas dengan tim produk, dan mendampingi engineer baru melalui review serta tujuan belajar.'
    candidate=guidebook.profile({},cv,'experienced')
    context={'uuid':str(uuid4()),'job_role':'Engineering Manager','level':'manager','industry':'Technology','company':'Synthetic Company',
        'language':'id','interviewer':'manager','panel':['manager'],'question_count':5,'cv_summary':{},
        'jd_summary':{'responsibilities':['Membantu pengembangan engineer, menetapkan prioritas, serta meninjau keputusan teknis dan risiko.']},
        'candidate_profile':candidate,'guidebook':guidebook.snapshot(),'assessment':assessment}
    prepared=await orchestrator.build_questions(context,{'manager':[]})
    assert {k for q in prepared['questions'] for k in q['competencies']}==set(assessment['weights'])
    report={'synthetic':True,'paid_llm_calls':True,'human_ratings':False,'validated':False,'rubric_version':assessment['version'],
        'rubric_sha256':assessment['sha256'],'ok':False,'prepared_competencies':[q['competencies'] for q in prepared['questions']],'cases':[]}
    cases=[('technical','Bagaimana Anda meninjau risiko migrasi layanan?',
        'Saya meminta engineer membandingkan migrasi bertahap dan sekaligus. Kami memeriksa risiko lock serta kegagalan dependensi lewat uji beban pada salinan data sintetis. Saya menyepakati batas error untuk rollback dan rollout bertahap dengan product owner. Dalam pilot ada lock panjang, sehingga urutan migrasi kami ubah. Setelah perubahan, pemeriksaan checksum cocok dan layanan tetap stabil dalam masa observasi.'),
        ('leadership','Bagaimana Anda membantu engineer mengembangkan kemampuan?',
        'Saya ingin membantu, tetapi belum punya contoh tindakan atau rencana yang bisa saya jelaskan.')]
    for index,(key,question,transcript) in enumerate(cases,1):
        source=[{'turn_id':f'synthetic-{index}','transcript':transcript}]
        data={**guidebook.role_context(context,'manager'),**evaluation_fields(assessment,[key]),'competencies':[key],
            'rubric':'\n'.join(line for line in assessment['rubric'].splitlines() if not line.startswith('| ') or line.split('|')[1].strip() in {key,'Kompetensi','---'}),
            'question':question,'transcript':transcript,'source_turns':source}
        raw=await orchestrator.evaluate(data)
        value=verified_scores(raw.get('competency_scores',{}),transcript,[key],source,assessment=assessment)[key]
        report['cases'].append({'competency':key,'status':value['status'],'score':value['score'],'indicators_met':value['indicators_met'],
            'indicator_evidence':value['indicator_evidence'],'next_level_gap':value['next_level_gap']})
        if key=='technical':assert value['status']=='measured' and value['indicator_evidence'],value
        else:assert value['status']=='insufficient',value
    report['ok']=True
    (ROOT/'artifacts/em-rubric-live-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'ok':True,'prepared_questions':5,'evaluated_synthetic_cases':2,'validated':False}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-paid',action='store_true');args=parser.parse_args()
    if not args.run_paid:parser.error('--run-paid wajib; memakai kredit LLM.')
    asyncio.run(run())
