const {test}=require('node:test'),assert=require('node:assert/strict'),{assess}=require('./check_js_dependencies.cjs');
const zero=()=>({metadata:{vulnerabilities:{critical:0,high:0,moderate:0,low:0,total:0}}});
test('critical/high runtime advisory blocks release',()=>{for(const key of ['critical','high']){const value=zero();value.metadata.vulnerabilities[key]=1;value.metadata.vulnerabilities.total=1;assert.equal(assess(value,zero()).runtime_gate_pass,false);}});
test('unavailable or malformed response never claims clean',()=>{for(const value of [null,{}, {metadata:{vulnerabilities:{high:'0',critical:0}}}])assert.equal(assess(value,zero()).runtime_gate_pass,false);});
test('dev advisories remain explicit and local audit never approves production',()=>{const full=zero();full.metadata.vulnerabilities.high=1;full.metadata.vulnerabilities.total=1;const value=assess(zero(),full);assert.ok(value.runtime_gate_pass&&value.dev_review_pending);assert.equal(value.production_accepted,false);});
