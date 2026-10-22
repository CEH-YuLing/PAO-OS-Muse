import test from 'node:test';
import assert from 'node:assert/strict';
import {settingsTeam} from './settings-team.mjs';
const id='11111111-1111-4111-8111-111111111111';
const sample=()=>({members:[{id,email:'person@example.test',role:'operator'}],brands:[{id,name:'Nhãn hàng'}],has_more:false});
test('native bounded metadata only, empty and partial observations allowed',()=>{
 assert.deepEqual(settingsTeam(sample()),sample());
 assert.deepEqual(settingsTeam({members:[],brands:[],has_more:true}),{members:[],brands:[],has_more:true});
});
test('reject missing, extra/private fields and truthy flags',()=>{
 for(const value of [null,[],{}, {...sample(),secret:'private'}, {...sample(),has_more:'false'}, {members:[],has_more:false}])assert.throws(()=>settingsTeam(value));
 const value=sample();value.members[0].token='private';assert.throws(()=>settingsTeam(value));
});
test('reject malformed identity, duplicate rows and unsupported roles',()=>{
 for(const mutate of [v=>v.members[0].id='bad',v=>v.members[0].email='x\nprivate',v=>v.members[0].role='viewer',v=>v.members.push({...v.members[0]}),v=>v.brands.push({...v.brands[0]}),v=>v.brands[0].name='',v=>v.members=Array(101).fill(v.members[0])]){
  const value=sample();mutate(value);assert.throws(()=>settingsTeam(value));
 }
});
