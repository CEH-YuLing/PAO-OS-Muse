import test from 'node:test';import assert from 'node:assert/strict';
import {featureLabel,coverageLabel,connectionLabel,runtimeLabel} from './display-status.mjs';
test('feature availability never treats truthy strings or missing data as ready',()=>{
 assert.equal(featureLabel(false),'Đang tắt');assert.equal(featureLabel(true),'Đã bật');
 for(const value of [null,undefined,'false','true',1])assert.equal(featureLabel(value),'Chưa xác minh');
});
test('missing dashboard data cannot report full coverage',()=>{
 for(const value of [null,undefined])assert.equal(coverageLabel(value),'Chưa có dữ liệu');
 for(const value of [{},{coverage_days:0,expected_days:0},{coverage_days:1,expected_days:2}])assert.equal(coverageLabel(value),'Cần kiểm tra');
 assert.equal(coverageLabel({coverage_days:7,expected_days:7}),'Đủ dữ liệu');
});
test('connection display translates without granting connection health',()=>{
 assert.equal(connectionLabel('configured'),'Đã cấu hình');assert.equal(connectionLabel('connected'),'Đã kết nối');
 assert.equal(connectionLabel('unknown_state'),'Trạng thái: unknown_state');
});
test('runtime labels are presentation-only, preserving unrecognized status',()=>{
 assert.equal(runtimeLabel('idle'),'Đang chờ');assert.equal(runtimeLabel('new_enum'),'new_enum');
});
