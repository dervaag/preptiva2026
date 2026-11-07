const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = {};
const context = vm.createContext({URL,document:{body:{dataset:{page:'test'}},querySelector:s=>elements[s] || null,querySelectorAll:()=>[]}});
vm.runInContext(fs.readFileSync('app/static/js/app.js','utf8'),context);
const evaluate = source => vm.runInContext(source,context);
assert.equal(evaluate("jobRubricEligible('  ENGINEERING   manager  ', 'single', 'manager')"),true);
for (const [role,mode,persona] of [['Product Manager','single','manager'],['Engineering Manager Senior','single','manager'],['Engineering Manager','panel','manager'],['Engineering Manager','single','hr']]) {
  context.testArgs={role,mode,persona};
  assert.equal(evaluate('jobRubricEligible(testArgs.role,testArgs.mode,testArgs.persona)'),false);
}
const checkbox={checked:true,disabled:false};
const container={hidden:false};
elements['#job-rubric-option']=container;
elements['[name=job_role]']={value:'Engineering Manager'};
elements['[name=interview_mode]']={value:'single'};
elements['[name=interviewer]:checked']={value:'manager'};
elements['[name=use_job_rubric]']=checkbox;
evaluate('updateJobRubricOption()');assert.equal(container.hidden,false);assert.equal(checkbox.checked,true);assert.equal(checkbox.disabled,false);
elements['[name=interview_mode]'].value='panel';evaluate('updateJobRubricOption()');
assert.equal(container.hidden,true);assert.equal(checkbox.checked,false);assert.equal(checkbox.disabled,true);
elements['[name=interview_mode]'].value='single';evaluate('updateJobRubricOption()');assert.equal(checkbox.checked,false);
checkbox.checked=true;elements['[name=interviewer]:checked'].value='hr';evaluate('updateJobRubricOption()');
assert.equal(container.hidden,true);assert.equal(checkbox.checked,false);assert.equal(checkbox.disabled,true);
elements['[name=interviewer]:checked'].value='manager';evaluate('updateJobRubricOption()');
assert.equal(container.hidden,false);assert.equal(checkbox.checked,false);assert.equal(checkbox.disabled,false);
checkbox.checked=true;elements['[name=job_role]'].value='Product Manager';evaluate('updateJobRubricOption()');
assert.equal(container.hidden,true);assert.equal(checkbox.checked,false);assert.equal(checkbox.disabled,true);
for (const url of ['javascript:alert(1)','data:text/html,<script>alert(1)</script>','https://u:p@example.com','http://example.com','/relative']) {
  context.source={source_title:'<img src=x onerror=alert(1)>',url};
  const html=evaluate('sourceLink(source)');
  assert.ok(!html.includes('<a '));assert.ok(!html.includes('<img'));
}
context.source={source_title:'Official source',url:'https://example.com/paper?query="quoted"'};
const anchor=evaluate('sourceLink(source)');assert.ok(anchor.includes('rel="noopener noreferrer"'));assert.ok(anchor.includes('https://example.com'));
context.score={status:'measured',score:3,indicators_met:['em.test.l3'],indicator_evidence:[{indicator_id:'em.test.l3',level:3,behavior:'Compare <alternatives>',quote:'Original "quote" <script>alert(1)</script>',turn_id:'q1'}],next_level_gap:'Need <evidence>',next_level_indicators:[{id:'em.test.l4',level:4,behavior:'Review trade-offs'}],sources:[{indicator_id:'em.test.l3',origin:'internal',source_title:'Source',url:'https://example.com',source_locator:'Page 1',source_excerpt:'A quote',application:'Internal application'}]};
const detail=evaluate('indicatorDetails(score)');
assert.ok(detail.includes('Alasan belum mencapai tingkat berikutnya'));assert.ok(detail.includes('Disusun internal'));
assert.ok(detail.includes('&lt;script&gt;'));assert.ok(!detail.includes('<script>'));
assert.equal(evaluate("indicatorDetails({status:'measured'})"),'');
assert.equal(evaluate('assessmentNotice({version:"old",validated:false})'),'');
context.assessment={profile_id:'engineering_manager_manager',title:'EM',status:'draft_pending_expert_review',job_reviewed_by_human:false,validated:false,scope:{job_roles:['Engineering Manager'],interviewer:'manager'}};
const notice=evaluate('assessmentNotice(assessment)');
assert.ok(notice.includes('belum ditinjau ahli'));assert.ok(notice.includes('belum divalidasi'));
console.log('UI helper checks passed: scope reset, legacy optional fields, escaped evidence, HTTPS-only source links, and draft labels.');
