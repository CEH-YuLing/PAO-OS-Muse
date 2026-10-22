import test from 'node:test';
import assert from 'node:assert/strict';
import {chatModelOptions,filterChatModels} from './chat-model-catalog.mjs';

const catalog={scope:'installation',engines:[{provider:'openai',installation_resource_id:'resource',error:null,
 models:['chat','image','unknown'],model_details:[
 {model:'chat',model_capabilities:{chat_supported:true,output_modalities:['text']}},
 {model:'image',model_capabilities:{chat_supported:false,output_modalities:['image']}},
 {model:'unknown',model_capabilities:{chat_supported:null,output_modalities:[]}},
 ]}]};
test('dedicated image model remains discoverable but cannot be selected as chat',()=>{
 const options=chatModelOptions(catalog,null,null);
 assert.equal(options.length,3);
 assert.equal(options.find(v=>v.selection.model==='image').available,false);
 assert.equal(options.find(v=>v.selection.model==='chat').available,true);
});
test('search and modality filters compose without mixing provider/source identities',()=>{
 const options=chatModelOptions(catalog,null,null);
 assert.deepEqual(filterChatModels(options,'','text').map(v=>v.selection.model),['chat']);
 assert.deepEqual(filterChatModels(options,'OpenAI','image').map(v=>v.selection.model),['image']);
 assert.deepEqual(filterChatModels(options,'','unknown').map(v=>v.selection.model),['unknown']);
 assert.equal(filterChatModels(options,'missing','text').length,0);
 assert.equal(options[0].selection.installation_resource_id,'resource');
});
