import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {THEME_KEY,THEME_BOOTSTRAP,readTheme,saveTheme,validTheme,resolveTheme,millisecondsUntilThemeChange,watchAutoTheme} from './theme.mjs';
test('appearance accepts manual light/dark plus optional auto mode',()=>{
  for(const value of ['dark','light','auto'])assert.ok(validTheme(value));
  for(const value of [null,undefined,'system','<script>','',{},123])assert.equal(validTheme(value),false);
});
test('existing dark appearance is the safe default',()=>{
  assert.equal(readTheme(null),'dark');assert.equal(readTheme({getItem:()=>'<script>'}),'dark');
  assert.equal(readTheme({getItem:()=>{throw Error('blocked')}}),'dark');
});
test('appearance persists only the dedicated non-sensitive key',()=>{
  const writes=[];const storage={setItem:(...values)=>writes.push(values)};
  assert.ok(saveTheme(storage,'light'));assert.deepEqual(writes,[[THEME_KEY,'light']]);
  assert.ok(saveTheme(storage,'auto'));assert.deepEqual(writes[1],[THEME_KEY,'auto']);
  assert.equal(saveTheme(storage,'token'),false);assert.equal(writes.length,2);
  assert.equal(saveTheme({setItem:()=>{throw Error('quota')}},'dark'),false);
});

test('automatic preference is read as auto, not persisted as the resolved colour',()=>{
  assert.equal(readTheme({getItem:()=> 'auto'}),'auto');
  assert.equal(readTheme(null,'light'),'light');
});

const local=(hour,minute=0,second=0,ms=0)=>new Date(2026,9,21,hour,minute,second,ms);
for(const [hour,minute,second,ms,expected] of [
  [0,0,0,0,'dark'],[5,59,59,999,'dark'],[6,0,0,0,'light'],
  [12,0,0,0,'light'],[17,59,59,999,'light'],[18,0,0,0,'dark'],[23,59,59,999,'dark'],
])test(`auto resolves local ${hour}:${minute}:${second}.${ms} to ${expected}`,()=>{
  assert.equal(resolveTheme('auto',local(hour,minute,second,ms)),expected);
});

test('manual selections never follow the clock',()=>{
  for(let hour=0;hour<24;hour++)for(const value of ['light','dark'])
    assert.equal(resolveTheme(value,local(hour)),value);
});

test('next boundary has exact millisecond precision and rolls over midnight',()=>{
  assert.equal(millisecondsUntilThemeChange(local(5,59,59,999)),1);
  assert.equal(millisecondsUntilThemeChange(local(17,59,59,999)),1);
  assert.equal(millisecondsUntilThemeChange(local(6)),12*60*60*1000);
  assert.equal(millisecondsUntilThemeChange(local(18)),12*60*60*1000);
  assert.equal(millisecondsUntilThemeChange(local(23,59)),(6*60+1)*60*1000);
  assert.equal(millisecondsUntilThemeChange(new Date(2026,11,31,23)),7*60*60*1000);
});

function fakeClock(initial){
  let instant=initial,sequence=0;
  const timers=new Map(),changes=[];
  const watcher=watchAutoTheme(value=>changes.push(value),{
    now:()=>new Date(instant),
    setTimeout:(callback,delay)=>{const id=++sequence;timers.set(id,{callback,delay});return id},
    clearTimeout:id=>timers.delete(id),
  });
  return {watcher,changes,timers,setTime:value=>{instant=value},tick(){
    const [id,{callback,delay}]=timers.entries().next().value;
    timers.delete(id);instant=new Date(instant.getTime()+delay);callback();
  }};
}

for(const hour of [6,18])test(`watcher switches at ${hour}:00 and cancels its timer on manual-mode cleanup`,()=>{
  const f=fakeClock(local(hour-1,59,59,999));
  assert.equal(f.timers.values().next().value.delay,1);
  f.tick();assert.deepEqual(f.changes,hour===6?['dark','light']:['light','dark']);
  assert.equal(f.timers.size,1);
  assert.equal(f.timers.values().next().value.delay,60_000);
  const staleCallback=f.timers.values().next().value.callback;
  f.watcher.stop();assert.equal(f.timers.size,0);
  staleCallback();f.watcher.refresh();assert.equal(f.changes.length,2);
});

test('wake/focus refresh uses current wall clock, not missed timer counts',()=>{
  const f=fakeClock(local(10));
  f.setTime(local(20));f.watcher.refresh();assert.equal(f.changes.at(-1),'dark');
  assert.equal(f.timers.size,1);
  f.setTime(local(7));f.watcher.refresh();assert.equal(f.changes.at(-1),'light');
  assert.equal(f.timers.size,1);f.watcher.stop();
});

test('foreground timer rechecks a clock/timezone edit within one minute',()=>{
  const f=fakeClock(local(11));f.setTime(local(22));f.tick();
  assert.equal(f.changes.at(-1),'dark');f.watcher.stop();
});

test('bootstrap and runtime agree for all hours and preserve auto preference',()=>{
  for(let hour=0;hour<24;hour++)for(const value of ['auto','light','dark']){
    const instant=local(hour),document={documentElement:{dataset:{},style:{}}};
    class DeviceDate extends Date {constructor(){super(instant.getTime())}}
    vm.runInNewContext(THEME_BOOTSTRAP,{document,Date:DeviceDate,localStorage:{getItem:()=>value}});
    assert.equal(document.documentElement.dataset.themePreference,value);
    assert.equal(document.documentElement.dataset.theme,resolveTheme(value,instant));
    assert.equal(document.documentElement.style.colorScheme,resolveTheme(value,instant));
  }
});
test('bootstrap applies preference before paint and tolerates storage denial',()=>{
  for(const value of ['light','dark','invalid',null]){
    const document={documentElement:{dataset:{},style:{}}};
    vm.runInNewContext(THEME_BOOTSTRAP,{document,localStorage:{getItem:key=>{assert.equal(key,THEME_KEY);return value}}});
    assert.equal(document.documentElement.dataset.theme,validTheme(value)?value:'dark');
    assert.equal(document.documentElement.style.colorScheme,validTheme(value)?value:'dark');
  }
  const document={documentElement:{dataset:{},style:{}}};
  vm.runInNewContext(THEME_BOOTSTRAP,{document,localStorage:{getItem(){throw Error('blocked')}}});
  assert.equal(document.documentElement.dataset.theme,'dark');
});
