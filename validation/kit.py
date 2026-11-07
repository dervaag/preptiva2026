"""Offline assessor workflow. Never invites people, invents ratings, or enables validated."""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def digest(dataset):
    cases = dataset['cases']
    if not cases or len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Dataset kosong atau ID kasus ganda.')
    if dataset.get('schema_version') == 2:
        assessment = dataset['assessment']
        if canonical_hash({k:v for k,v in assessment.items() if k != 'sha256'}) != assessment['sha256']:
            raise ValueError('Snapshot rubrik berubah atau hash tidak cocok.')
        if dataset['rubric_sha256'] != assessment['sha256'] or dataset['rubric'] != assessment['rubric'] or dataset['rubric_version'] != assessment['version']:
            raise ValueError('Metadata rubrik berbeda dari snapshot.')
        if dataset['job_role'] not in assessment['scope']['job_roles'] or dataset['interviewer'] != assessment['scope']['interviewer']:
            raise ValueError('Konteks pekerjaan tidak sesuai ruang lingkup rubrik.')
        for case in cases:
            if case['split'] not in ('calibration', 'test') or case['competency'] not in assessment['competency_definitions']:
                raise ValueError('Split atau kompetensi kasus tidak valid.')
        visible = {k:dataset[k] for k in ('schema_version','dataset_id','synthetic','purpose','job_role','interviewer','level','assessment')}
        visible['cases'] = [{k:c[k] for k in ('id','split','competency','language','question','transcript')} for c in cases]
        return canonical_hash(visible)
    # Preserve legacy packet hashes so already distributed general packets remain importable.
    if hashlib.sha256(dataset['rubric'].encode()).hexdigest() != dataset['rubric_sha256']:
        raise ValueError('Isi rubrik tidak cocok dengan hash snapshot.')
    visible = {'rubric_version':dataset['rubric_version'],'rubric_sha256':dataset['rubric_sha256'],
        'job_role':dataset['job_role'],'interviewer':dataset['interviewer'],'level':dataset['level'],
        'cases':[{k:c[k] for k in ('id','competency','language','question','transcript')} for c in cases]}
    return hashlib.sha256(json.dumps(visible,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def write_private(path, text):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as file:
        path.chmod(0o600);file.write(text)

def _general_starter():
    rubric=(ROOT/'docs/assessment-reference.md').read_text().split('<!-- rubric:start -->')[1].split('<!-- rubric:end -->')[0].strip()
    samples=[
        ('communication','id','Bagaimana Anda menjelaskan risiko keterlambatan kepada stakeholder?',
         'Saya menjelaskan bahwa dua dependensi belum selesai. Saya memisahkan fitur wajib dan tambahan, lalu menunjukkan jadwal untuk kedua pilihan. Tim bisnis memilih fitur wajib; saya mengirim pembaruan kemajuan tiap dua hari.'),
        ('problem_solving','id','Apa langkah Anda ketika layanan sering gagal setelah rilis?',
         'Saya langsung meminta tim menambah server karena menurut saya kapasitas pasti kurang. Kami tidak memeriksa log atau membandingkan perubahan konfigurasi. Setelah server ditambah, kegagalan masih terjadi dan penyebabnya belum diketahui.'),
        ('technical','en','How did you reduce risk in a database migration?',
         'We first rehearsed on an anonymized production-sized copy. I asked the team to measure locks and compare row counts and checksums. We defined a rollback condition and ran a small batch before increasing traffic. The rehearsal exposed a long lock, so we changed the migration sequence.'),
        ('analytical','mixed','Bagaimana Anda memilih alternatif saat data eksperimen terbatas?',
         'Sample kami hanya dua belas pengguna, jadi saya tidak menganggap kenaikan conversion sebagai kepastian. We compared completion rates and failure reasons, lalu mencatat kemungkinan bias rekrutmen. Saya memilih pilot kecil dan menentukan data tambahan sebelum rollout.'),
        ('teamwork','id','Bagaimana Anda menangani perbedaan prioritas antaranggota tim?',
         'Saya mengundang rekan produk dan engineering menjelaskan kendala masing-masing. Peran saya mencatat dependensi dan menyusun dua pilihan urutan kerja. Kami menyepakati tanggung jawab serta waktu pemeriksaan ulang. Saya belum mengukur apakah cara ini mengurangi konflik berikutnya.'),
        ('adaptability','en','Tell us about a plan you changed after receiving new information.',
         'When the integration partner changed its interface, I asked the team to keep the old deadline. I did not review the estimate or test an alternative. We discovered additional work near release and postponed the delivery.'),
        ('leadership','id','Bagaimana Anda mengembangkan anggota tim sambil menjaga pengiriman?',
         'Saya memberi seorang engineer kesempatan memimpin pekerjaan kecil, menyepakati batas keputusan dan pasangan reviewer. Kami meninjau progres setiap minggu. Setelah dua iterasi ia mampu mengoordinasikan dependensi sendiri; saya masih perlu menguji pendekatan ini pada proyek yang lebih kompleks.')]
    return {'dataset_id':str(uuid4()),'synthetic':True,'purpose':'starter packet; not a validation sample',
        'job_role':'Engineering Manager','interviewer':'manager','level':'manager','job_reviewed_by_human':False,
        'rubric_version':'2026-11-05.2','rubric_sha256':hashlib.sha256(rubric.encode()).hexdigest(),'rubric':rubric,
        'model':None,'validated':False,'cases':[{'id':f'em-{i:03}','split':'test','competency':key,'language':language,
            'question':question,'transcript':transcript,'human_ratings':{},'consensus_score':None,'ai_runs':[],'ai_quotes':[]}
            for i,(key,language,question,transcript) in enumerate(samples,1)]}



def starter(profile='general'):
    if profile == 'general':
        return _general_starter()
    if profile != 'engineering-manager':
        raise ValueError('Profil tidak dikenal.')
    from app.ai.job_rubric import snapshot_profile
    from validation.em_cases import SAMPLES
    assessment = snapshot_profile()
    dataset = {'schema_version':2,'dataset_id':str(uuid4()),'synthetic':True,
        'purpose':'draft workflow starter; not a gold set or adequate validation sample',
        'job_role':'Engineering Manager','interviewer':'manager','level':'manager',
        'job_reviewed_by_human':False,'assessment':assessment,
        'rubric_version':assessment['version'],'rubric_sha256':assessment['sha256'],'rubric':assessment['rubric'],
        'model':None,'validated':False,'cases':[]}
    for i,(key,language,split,question,transcript) in enumerate(SAMPLES,1):
        dataset['cases'].append({'id':f'em-draft-{i:03}','split':split,'competency':key,'language':language,
            'question':question,'transcript':transcript,'human_ratings':{},'human_evidence':{},
            'consensus_score':None,'ai_runs':[],'ai_quotes':[]})
    digest(dataset)
    return dataset


def packet(dataset, assessor):
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,50}',assessor):
        raise ValueError('Gunakan pseudonim asesor 2–50 huruf/angka/-/_.')
    visible = {'dataset_hash':digest(dataset),'assessor_id':assessor,'assignment_id':str(uuid4()),
        'synthetic':dataset.get('synthetic',False),'rubric_version':dataset['rubric_version'],
        'job_role':dataset['job_role'],'level':dataset['level'],'rubric':dataset['rubric'],
        'profile_status':dataset.get('assessment',{}).get('status'),
        'competency_definitions':dataset.get('assessment',{}).get('competency_definitions',{}),
        'sources':dataset.get('assessment',{}).get('sources',[]),
        'cases':[{k:c[k] for k in ('id','competency','language','question','transcript')} for c in dataset['cases']]}
    # Split labels stay in the coordinator file; raters see neither expected performance nor AI scores.
    encoded=json.dumps(visible,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return (ROOT/'validation/packet.html').read_text().replace('__PACKET_JSON__',encoded)


def expertise_review_template(dataset):
    digest(dataset)
    assessment=dataset.get('assessment',{})
    if not assessment.get('competency_definitions'):
        raise ValueError('Template tinjauan ahli memerlukan profil rubrik terstruktur.')
    return {'type':'expertise_review_template','dataset_hash':digest(dataset),
        'rubric_version':assessment['version'],'rubric_sha256':assessment['sha256'],
        'reviewer_id':'','reviewer_role':'','relevant_job_experience':'','reviewed_at':None,
        'review_completed':False,'job_reviewed_by_human':False,'validated':False,
        'instructions':'Isian kosong untuk ahli pekerjaan. Data reference adalah draf yang ditinjau, bukan persetujuan ahli. Template ini tidak mengubah status rubrik secara otomatis.',
        'scope_reference':assessment['scope'],
        'scope_review':{'suitable':None,'missing_responsibilities':'','comments':''},
        'job_source_reviews':[{'source_id':source['id'],'title':source['title'],'url':source['url'],
            'locator':source['locator'],'relevant_to_target_job':None,'comments':''}
            for source in assessment['sources'] if source['id'] in {s for task in assessment['job_analysis'] for s in task['source_ids']}],
        'responsibility_reviews':[{'reference':task,'appropriate':None,'suggested_change':'','rationale':''}
            for task in assessment['job_analysis']],
        'competency_weight_reviews':[{'competency':key,'name':definition['name'],
            'weight_reference':assessment['weights'][key],'decision':'','suggested_weight':None,'rationale':''}
            for key,definition in assessment['competency_definitions'].items()],
        'indicator_reviews':[{'competency':key,'level':int(level),'indicator_id':anchor['id'],
            'reference':anchor,'behavior_clear':None,'job_relevant':None,'source_mapping_appropriate':None,
            'distinguishable_from_adjacent_levels':None,'suggested_rewording':'','rationale':''}
            for key,definition in assessment['competency_definitions'].items() for level,anchor in definition['levels'].items()],
        'overall_recommendation':'','follow_up_actions':''}


def validate_rating(dataset, case, row):
    status,score = row.get('status'),row.get('score')
    if status not in ('measured','insufficient') or (status=='measured' and (type(score) is not int or score not in range(1,6))) or (status=='insufficient' and score is not None):
        raise ValueError('Skor/status penilaian tidak valid.')
    quote = row.get('quote','')
    if not isinstance(quote,str) or (quote and quote not in case['transcript']):
        raise ValueError('Kutipan harus ada persis dalam jawaban.')
    if status == 'measured' and len(quote.strip()) < 8:
        raise ValueError('Skor harus disertai kutipan asli minimal delapan karakter.')
    rationale=row.get('rationale','')
    if not isinstance(rationale,str) or len(rationale.strip()) < 10:
        raise ValueError('Tuliskan alasan penilaian minimal 10 karakter.')
    indicators=row.get('indicators_met',[])
    gap=row.get('next_level_gap','')
    definitions=dataset.get('assessment',{}).get('competency_definitions',{})
    if definitions:
        if not isinstance(indicators,list) or len(set(indicators)) != len(indicators):
            raise ValueError('Daftar indikator tidak valid.')
        if status == 'measured':
            expected=definitions[case['competency']]['levels'][str(score)]['id']
            if indicators != [expected]:
                raise ValueError('Indikator harus berasal dari kompetensi dan tingkat skor yang dipilih.')
            if not isinstance(gap,str) or (score < 5 and len(gap.strip()) < 10) or (score == 5 and gap.strip()):
                raise ValueError('Jelaskan bukti yang belum ada untuk tingkat berikutnya; skor 5 tidak memiliki tingkat berikutnya.')
        elif indicators:
            raise ValueError('Bukti kurang tidak boleh menyatakan indikator tercapai.')
    return {'status':status,'quote':quote,'rationale':rationale,'indicators_met':indicators,'next_level_gap':gap}


def merge(dataset, ratings):
    expected=digest(dataset);cases={c['id']:c for c in dataset['cases']};seen=set()
    result=json.loads(json.dumps(dataset));out={c['id']:c for c in result['cases']}
    for rating in ratings:
        assessor=rating.get('assessor_id')
        if not isinstance(assessor,str) or not re.fullmatch(r'[A-Za-z0-9_-]{2,50}',assessor) or assessor in seen:
            raise ValueError('Pseudonim asesor kosong, tidak valid, atau ganda.')
        seen.add(assessor)
        if rating.get('dataset_hash') != expected or rating.get('personally_rated_independently') is not True:
            raise ValueError('Versi dataset berbeda atau pernyataan penilaian independen belum diisi.')
        rows=rating.get('ratings',[])
        if len(rows)!=len(cases) or {r.get('case_id') for r in rows}!=set(cases):
            raise ValueError('Daftar kasus tidak lengkap atau ganda.')
        for row in rows:
            evidence=validate_rating(dataset,cases[row['case_id']],row)
            case=out[row['case_id']]
            if assessor in case.get('human_ratings',{}):
                raise ValueError('Penilaian asesor sudah ada; tidak boleh ditimpa.')
            case.setdefault('human_ratings',{})[assessor]=row['score']
            case.setdefault('human_evidence',{})[assessor]=evidence
        result.setdefault('rating_imports',[]).append({'assessor_id':assessor,
            'assignment_id':rating.get('assignment_id'),'submitted_at':rating.get('submitted_at'),
            'imported_at':datetime.now(timezone.utc).isoformat(),'personally_rated_independently':True,
            'identity_verified_by_tool':False})
    result['validated']=False
    result['assessor_count']=len({r for c in result['cases'] for r in c.get('human_ratings',{})})
    result['pending']=['Verifikasi kualifikasi dan independensi asesor oleh koordinator',
        'Tinjau indikator/kompetensi pekerjaan bersama ahli','Tetapkan konsensus setelah penilaian independen',
        'Jalankan AI lima kali','Tinjau cakupan, fairness dan sensitivitas STT']
    return result


def independent_hash(dataset):
    return canonical_hash([{'id':c['id'],'ratings':c.get('human_ratings',{}),
        'evidence':c.get('human_evidence',{})} for c in dataset['cases']])


def require_independent_ratings(dataset):
    digest(dataset)
    raters = sorted(dataset['cases'][0].get('human_ratings',{}))
    if len(raters) < 3:
        raise ValueError('Konsensus memerlukan minimal tiga asesor independen terlebih dahulu.')
    for case in dataset['cases']:
        if sorted(case.get('human_ratings',{})) != raters:
            raise ValueError('Setiap kasus harus dinilai asesor yang sama.')
        for rater,score in case['human_ratings'].items():
            if score is not None and (type(score) is not int or score not in range(1,6)):
                raise ValueError('Skor independen tidak valid.')
            if dataset.get('schema_version') == 2:
                evidence=case.get('human_evidence',{}).get(rater,{})
                validate_rating(dataset,case,{**evidence,'score':score})
    return raters


def consensus_template(dataset):
    raters=require_independent_ratings(dataset)
    return {'dataset_hash':digest(dataset),'independent_ratings_hash':independent_hash(dataset),
        'coordinator_id':'','reviewed_independent_ratings':False,'validated':False,
        'instructions':'Isi keputusan setelah pembahasan. Jangan menghitung atau mengisi konsensus otomatis. Skor independen tetap dipertahankan.',
        'assessor_ids':raters,'decisions':[{'case_id':c['id'],'status':'','score':None,
            'quote':'','indicators_met':[],'rationale':'','next_level_gap':''} for c in dataset['cases']]}


def apply_consensus(dataset, decision):
    require_independent_ratings(dataset)
    if decision.get('dataset_hash') != digest(dataset) or decision.get('independent_ratings_hash') != independent_hash(dataset):
        raise ValueError('Dataset atau penilaian independen berubah setelah template konsensus dibuat.')
    coordinator=decision.get('coordinator_id','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,50}',coordinator) or decision.get('reviewed_independent_ratings') is not True:
        raise ValueError('Koordinator dan pernyataan tinjauan harus diisi.')
    rows=decision.get('decisions',[]);cases={c['id']:c for c in dataset['cases']}
    if len(rows)!=len(cases) or {r.get('case_id') for r in rows} != set(cases):
        raise ValueError('Keputusan konsensus harus mencakup semua kasus tanpa duplikasi.')
    result=json.loads(json.dumps(dataset));out={c['id']:c for c in result['cases']}
    for row in rows:
        case=out[row['case_id']]
        if case.get('consensus_score') is not None or 'consensus_status' in case:
            raise ValueError('Konsensus sudah ada; tidak boleh ditimpa.')
        evidence=validate_rating(dataset,case,row)
        case.update(consensus_score=row['score'],consensus_status=row['status'],consensus_evidence=evidence)
    result['consensus_audit']={'coordinator_id':coordinator,'reviewed_independent_ratings':True,
        'independent_ratings_hash':independent_hash(dataset),'recorded_at':datetime.now(timezone.utc).isoformat(),
        'identity_verified_by_tool':False}
    result['validated']=False
    return result


async def run_ai(dataset):
    from app.ai import orchestrator
    from app.ai.scoring import verified_scores
    from app.config import settings
    digest(dataset)
    if any(c.get('ai_runs') for c in dataset['cases']):
        raise ValueError('Hasil AI sudah ada; simpan dataset baru untuk run terpisah.')
    result=json.loads(json.dumps(dataset));result['model']=settings.model_deep
    result['ai_provenance']={'runs_per_case':5,'model':settings.model_deep,
        'evaluator_module_sha256':hashlib.sha256(Path(orchestrator.__file__).read_bytes()).hexdigest(),
        'started_at':datetime.now(timezone.utc).isoformat(),'contains_human_scores_in_prompt':False}
    assessment=dataset.get('assessment')
    for case in result['cases']:
        if case.get('ai_runs'):
            raise ValueError('Hasil AI sudah ada; simpan dataset baru untuk run terpisah.')
        case['ai_runs'],case['ai_quotes'],case['ai_statuses'],case['ai_details']=[],[],[],[]
        # Use the same competency-row filtering as the runtime finalization worker.
        rubric='\n'.join(line for line in dataset['rubric'].splitlines()
            if not line.startswith('| ') or line.split('|')[1].strip() in {case['competency'],'Kompetensi','---'})
        for _ in range(5):
            context={'interviewer':dataset['interviewer'],'job_role':dataset['job_role'],'level':dataset['level'],
                'language':case['language'] if case['language'] in ('id','en') else 'id','question':case['question'],
                'transcript':case['transcript'],'competencies':[case['competency']], 'rubric':rubric,
                'source_turns':[{'turn_id':case['id'],'transcript':case['transcript']}]}
            if assessment:
                from app.ai.job_rubric import evaluation_fields
                context.update(evaluation_fields(assessment,[case['competency']]))
            case['ai_prompt_context_sha256']=canonical_hash({'evaluator_module_sha256':result['ai_provenance']['evaluator_module_sha256'],'context':context})
            raw=await orchestrator.evaluate(context)
            kwargs={'assessment':assessment} if assessment else {}
            verified=verified_scores(raw.get('competency_scores',{}),case['transcript'],[case['competency']],context['source_turns'],**kwargs)[case['competency']]
            score=verified['score'] if verified['status']=='measured' else None
            if score is not None and float(score).is_integer(): score=int(score)
            case['ai_runs'].append(score);case['ai_statuses'].append(verified['status'])
            case['ai_quotes']+=verified['evidence'];case['ai_details'].append(verified)
        print('Evaluated:',case['id'],flush=True)
    result['validated']=False
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--output',type=Path,required=True)
    init.add_argument('--profile',choices=('general','engineering-manager'),default='general')
    pack=sub.add_parser('pack');pack.add_argument('dataset',type=Path);pack.add_argument('--assessor',required=True);pack.add_argument('--output',type=Path,required=True)
    review=sub.add_parser('expertise-review-template');review.add_argument('dataset',type=Path);review.add_argument('--output',type=Path,required=True)
    combine=sub.add_parser('merge');combine.add_argument('dataset',type=Path);combine.add_argument('ratings',type=Path,nargs='+');combine.add_argument('--output',type=Path,required=True)
    template=sub.add_parser('consensus-template');template.add_argument('dataset',type=Path);template.add_argument('--output',type=Path,required=True)
    consensus=sub.add_parser('consensus');consensus.add_argument('dataset',type=Path);consensus.add_argument('decision',type=Path);consensus.add_argument('--output',type=Path,required=True)
    ai=sub.add_parser('run-ai');ai.add_argument('dataset',type=Path);ai.add_argument('--output',type=Path,required=True);ai.add_argument('--run-paid',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='init': result=starter(args.profile)
        else:
            dataset=json.loads(args.dataset.read_text())
            if args.command=='pack':
                write_private(args.output,packet(dataset,args.assessor));print('Blind packet written:',args.output);return
            if args.command=='merge': result=merge(dataset,[json.loads(p.read_text()) for p in args.ratings])
            elif args.command=='expertise-review-template': result=expertise_review_template(dataset)
            elif args.command=='consensus-template': result=consensus_template(dataset)
            elif args.command=='consensus': result=apply_consensus(dataset,json.loads(args.decision.read_text()))
            else:
                if not args.run_paid: parser.error('--run-paid wajib; perintah memakai kredit LLM.')
                import asyncio
                result=asyncio.run(run_ai(dataset))
        write_private(args.output,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('Written:',args.output,'; validated remains false.')
    except (ValueError,KeyError,TypeError,FileExistsError) as exc:
        parser.error(str(exc))

if __name__=='__main__':main()
