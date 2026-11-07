"""Offline blind assessor packets. No account invitations or automatic validation claims."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def digest(dataset):
    if hashlib.sha256(dataset['rubric'].encode()).hexdigest() != dataset['rubric_sha256']:
        raise ValueError('Isi rubrik tidak cocok dengan hash snapshot.')
    if not dataset['cases'] or len({c['id'] for c in dataset['cases']}) != len(dataset['cases']):
        raise ValueError('Dataset kosong atau ID kasus ganda.')
    visible = {'rubric_version':dataset['rubric_version'],'rubric_sha256':dataset['rubric_sha256'],
        'job_role':dataset['job_role'],'interviewer':dataset['interviewer'],'level':dataset['level'],
        'cases':[{k:c[k] for k in ('id','competency','language','question','transcript')} for c in dataset['cases']]}
    return hashlib.sha256(json.dumps(visible,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def write_private(path, text):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as file:
        path.chmod(0o600);file.write(text)


def starter():
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


def packet(dataset, assessor):
    if not re.fullmatch(r'[A-Za-z0-9_-]{2,50}',assessor):
        raise ValueError('Gunakan pseudonim asesor 2–50 huruf/angka/-/_.')
    visible={'dataset_hash':digest(dataset),'assessor_id':assessor,'assignment_id':str(uuid4()),
        'synthetic':dataset.get('synthetic',False),
        'rubric_version':dataset['rubric_version'],'job_role':dataset['job_role'],'level':dataset['level'],
        'rubric':dataset['rubric'],'cases':[{k:c[k] for k in ('id','competency','language','question','transcript')} for c in dataset['cases']]}
    encoded=json.dumps(visible,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(ROOT/'validation/packet.html').read_text()
    return template.replace('__PACKET_JSON__',encoded)


def merge(dataset, ratings):
    expected=digest(dataset);cases={c['id']:c for c in dataset['cases']};seen=set()
    result=json.loads(json.dumps(dataset));out={c['id']:c for c in result['cases']}
    for rating in ratings:
        assessor=rating.get('assessor_id')
        if not assessor or assessor in seen:
            raise ValueError('Pseudonim asesor kosong atau ganda.')
        seen.add(assessor)
        if rating.get('dataset_hash') != expected or rating.get('personally_rated_independently') is not True:
            raise ValueError('Versi dataset berbeda atau pernyataan penilaian independen belum diisi.')
        rows=rating.get('ratings',[])
        if len(rows)!=len(cases) or {r.get('case_id') for r in rows}!=set(cases):
            raise ValueError('Daftar kasus tidak lengkap atau ganda.')
        for row in rows:
            status,score=row.get('status'),row.get('score')
            if status not in ('measured','insufficient') or (status=='measured' and (type(score) is not int or score not in range(1,6))) or (status=='insufficient' and score is not None):
                raise ValueError('Skor/status penilaian tidak valid.')
            quote=row.get('quote','')
            if status=='measured' and (not isinstance(quote,str) or len(quote.strip())<8 or quote not in cases[row['case_id']]['transcript']):
                raise ValueError('Skor harus disertai kutipan asli yang ada dalam jawaban.')
            if not isinstance(row.get('rationale'),str) or len(row['rationale'].strip())<10:
                raise ValueError('Tuliskan alasan penilaian minimal 10 karakter.')
            case=out[row['case_id']]
            if assessor in case.get('human_ratings',{}):
                raise ValueError('Penilaian asesor sudah ada; tidak boleh ditimpa.')
            case.setdefault('human_ratings',{})[assessor]=score
            case.setdefault('human_evidence',{})[assessor]={'status':status,'quote':quote,'rationale':row['rationale']}
    result['validated']=False
    result['assessor_count']=len({r for c in result['cases'] for r in c.get('human_ratings',{})})
    result['pending']=['Verifikasi identitas/independensi asesor oleh koordinator','Tetapkan konsensus setelah penilaian independen','Jalankan AI lima kali','Tinjau cakupan, fairness dan sensitivitas STT']
    return result


async def run_ai(dataset):
    from app.ai import orchestrator
    from app.ai.scoring import verified_scores
    from app.config import settings
    digest(dataset)
    result=json.loads(json.dumps(dataset));result['model']=settings.model_deep
    for case in result['cases']:
        case['ai_runs'],case['ai_quotes'],case['ai_statuses']=[],[],[]
        for _ in range(5):
            context={'interviewer':dataset['interviewer'],'job_role':dataset['job_role'],'level':dataset['level'],
                'language':case['language'] if case['language'] in ('id','en') else 'id','question':case['question'],
                'transcript':case['transcript'],'competencies':[case['competency']], 'rubric':dataset['rubric'],
                'source_turns':[{'turn_id':case['id'],'transcript':case['transcript']}]}
            raw=await orchestrator.evaluate(context)
            verified=verified_scores(raw.get('competency_scores',{}),case['transcript'],[case['competency']],context['source_turns'])[case['competency']]
            score=verified['score'] if verified['status']=='measured' else None
            if score is not None and float(score).is_integer(): score=int(score)
            case['ai_runs'].append(score)
            case['ai_statuses'].append(verified['status']);case['ai_quotes']+=verified['evidence']
        print('Evaluated:',case['id'],flush=True)
    result['validated']=False
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init');init.add_argument('--output',type=Path,required=True)
    pack=sub.add_parser('pack');pack.add_argument('dataset',type=Path);pack.add_argument('--assessor',required=True);pack.add_argument('--output',type=Path,required=True)
    combine=sub.add_parser('merge');combine.add_argument('dataset',type=Path);combine.add_argument('ratings',type=Path,nargs='+');combine.add_argument('--output',type=Path,required=True)
    ai=sub.add_parser('run-ai');ai.add_argument('dataset',type=Path);ai.add_argument('--output',type=Path,required=True);ai.add_argument('--run-paid',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='init': result=starter()
        else:
            dataset=json.loads(args.dataset.read_text())
            if args.command=='pack':
                write_private(args.output,packet(dataset,args.assessor));print('Blind packet written:',args.output);return
            if args.command=='merge': result=merge(dataset,[json.loads(p.read_text()) for p in args.ratings])
            else:
                if not args.run_paid: parser.error('--run-paid wajib; perintah memakai kredit LLM.')
                import asyncio,sys
                sys.path.insert(0,str(ROOT))
                result=asyncio.run(run_ai(dataset))
        write_private(args.output,json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('Written:',args.output,'; validated remains false.')
    except (ValueError,KeyError,TypeError,FileExistsError) as exc:
        parser.error(str(exc))

if __name__=='__main__':main()
