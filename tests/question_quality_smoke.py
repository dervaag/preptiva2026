"""Opt-in real LLM checks with synthetic CV/JD; no TTS, STT or production DB writes."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.ai import orchestrator, guidebook
from app.ai.blueprint import forbidden_hr, blueprint

FRESH = ('Lulusan baru S1 Akuntansi, belum pernah bekerja penuh waktu. Proyek kuliah menyusun laporan keuangan '
         'koperasi kampus bersama empat teman. Menjadi bendahara organisasi mahasiswa dan mengatur anggaran acara. '
         'Magang administrasi tiga bulan membantu mencocokkan bukti transaksi. Saya belajar dari masukan dosen '
         'dan memperbaiki pembagian tugas ketika laporan kelompok terlambat.')
EXPERIENCED = ('Akuntan dengan pengalaman kerja empat tahun di perusahaan distribusi. Bertanggung jawab atas '
               'rekonsiliasi bank, penyusunan laporan bulanan, koordinasi bukti transaksi dengan tim penjualan, '
               'dan perbaikan proses penutupan buku. Melatih dua rekan baru menggunakan daftar periksa kualitas. '
               'Proyek terakhir mengurangi transaksi tanpa bukti dengan prosedur verifikasi lintas tim.')
JD = ('Posisi Akuntan: menyusun laporan keuangan, memeriksa kelengkapan bukti transaksi, melakukan rekonsiliasi '
      'dan berkoordinasi dengan rekan lintas fungsi. Ketelitian, komunikasi dan integritas penting. '
      'Tidak memerlukan pengalaman pemrograman.')


async def main(selected=None):
    report = {'synthetic_data': True, 'paid_llm_calls': True, 'tts_stt_calls': False, 'validated_for_selection': False, 'cases': [], 'ok': False}
    for name, cv, roles, count in [('fresh_hr', FRESH, ['hr'], 5), ('experienced_user', EXPERIENCED, ['user'], 3),
                                  ('fresh_panel', FRESH, ['hr', 'user', 'manager'], 3)]:
        if selected and name != selected:
            continue
        parsed = await orchestrator.parse_documents(cv, JD)
        candidate = guidebook.profile(parsed['cv_summary'], cv)
        assert candidate['career_stage'] == ('experienced' if name == 'experienced_user' else 'fresh_graduate'), json.dumps({'candidate':candidate,'extracted_stage':parsed['cv_summary'].get('career_stage'), 'stage_evidence':parsed['cv_summary'].get('career_stage_evidence')}, ensure_ascii=False)
        context = {**parsed, 'uuid':str(uuid4()), 'question_count':count, 'interviewer':roles[0], 'panel':roles,
                   'job_role':'Akuntan', 'level':'middle' if name == 'experienced_user' else 'junior',
                   'industry':'Distribusi', 'language':'id', 'candidate_profile':candidate, 'guidebook':guidebook.snapshot()}
        if name == 'fresh_hr':
            for seed in range(10000):
                context['uuid'] = 'quality-hr-' + str(seed)
                intents = {slot['intent_id'] for slot in blueprint(count, context['uuid'], roles, context['guidebook'])}
                if {'hr.motivation', 'hr.initiative', 'hr.setback'} <= intents:
                    break
        prepared = await orchestrator.build_questions(context, {p:[] for p in roles})
        case = {'name':name,'career_stage':candidate['career_stage'],'questions':[
            {'interviewer':p['interviewer'], 'intent_id':p['intent_id'], **q} for p,q in zip(prepared['plan'],prepared['questions'])]}
        for q in case['questions']:
            if q['interviewer'] == 'hr': assert not forbidden_hr(q['question_text']) and 'technical' not in q['competencies']
        next_role = prepared['plan'][1]['interviewer']
        answer = ('Saya membahas pekerjaan rekonsiliasi bank; masalah utamanya dokumen penjualan terlambat.' if name == 'experienced_user' else
                  'Saya belum pernah bekerja tetap. Dalam proyek koperasi kampus, seorang teman terlambat mengirim bukti transaksi. '
                  'Saya mengajak diskusi pembagian tugas dan meminta masukan dosen; hasilnya kami menyelesaikan laporan tepat waktu.')
        dynamic = {**guidebook.role_context(context, next_role), 'planned_question':prepared['questions'][1],
                   'intent':prepared['plan'][1], 'asked_questions':[prepared['questions'][0]['question_text']],
                   'conversation':[{'interviewer':roles[0], 'question':prepared['questions'][0]['question_text'], 'answer':answer}]}
        case['adaptive_next'] = await orchestrator.adapt_question(dynamic)
        case['guidebook_sha256'] = context['guidebook']['sha256']
        report['cases'].append(case)
        (ROOT/'artifacts/question-quality-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print('Verified synthetic case:', name, flush=True)
    report['ok'] = True
    (ROOT/'artifacts/question-quality-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Real LLM checks passed; review synthetic question examples in artifacts/question-quality-smoke.json.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-paid', action='store_true')
    parser.add_argument('--case', choices=['fresh_hr','experienced_user','fresh_panel'])
    args = parser.parse_args()
    if not args.run_paid:
        raise SystemExit('Use --run-paid explicitly; this consumes LLM provider credits.')
    asyncio.run(main(args.case))
