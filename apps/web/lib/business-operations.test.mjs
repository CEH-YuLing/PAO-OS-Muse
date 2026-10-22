import test from 'node:test';
import assert from 'node:assert/strict';
import {activeBusinessJobs,businessJobLabel,businessProgress,pollBusinessOperations} from './business-operations.mjs';
test('cancel request remains pending until terminal server state',()=>{
  for(const status of ['queued','running']) assert.match(businessJobLabel({status,cancel_requested:true}),/chờ xác nhận/);
  assert.equal(businessJobLabel({status:'cancelled',cancel_requested:true}),'Đã hủy');
  assert.equal(businessJobLabel({status:'completed',cancel_requested:true}),'Đã tạo bản nháp');
});
test('unknown job states fail closed in presentation',()=>{
  assert.equal(businessJobLabel({status:'mystery'}),'Trạng thái chưa xác minh');
  assert.equal(activeBusinessJobs([{status:'mystery'}]),false);
});
test('progress separates draft completion from effective approval',()=>{
  assert.deepEqual(businessProgress([{status:'completed',content_decision:null},{status:'completed',content_decision:'approve',content_approved:false},{status:'completed',content_decision:'reject'},{status:'running',cancel_requested:true},{status:'failed'},{status:'cancelled'}]),
    {active:1,pendingCancel:1,waitingReview:1,approved:0,needsRework:3});
  assert.equal(businessProgress([{status:'completed',content_approved:true,content_decision:'approve'}]).approved,1);
  assert.equal(businessProgress().active,0);
});
test('poll only active visible online confirmed scope; never retry mutations',()=>{
  const active=[{status:'queued'}],allowed={visible:true,online:true,unknown:false,busy:false};
  assert.equal(pollBusinessOperations(active,allowed),true);
  for(const state of [{visible:false},{online:false},{unknown:true},{busy:true}]) assert.equal(pollBusinessOperations(active,{...allowed,...state}),false);
  assert.equal(pollBusinessOperations([{status:'completed'}],allowed),false);
  assert.equal(pollBusinessOperations([],allowed),false);
});
