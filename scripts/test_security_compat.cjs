// Native compatibility checks for the reviewed dependency overrides, no network or app data.
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
test('Next resolves the reviewed PostCSS patch and processes ordinary CSS',()=>{
 const resolved=require.resolve('postcss',{paths:[path.dirname(require.resolve('next/package.json'))]});
 const postcss=require(resolved);assert.equal(postcss().version,'8.5.30');assert.ok(postcss.parse('a { color: red; }').toString().includes('color: red'));
});
for(const format of ['webp','avif'])test('Next native image optimizer works with patched Sharp: '+format,async()=>{
 const sharp=require('sharp'),{optimizeImage}=require('next/dist/server/image-optimizer');
 assert.equal(sharp.versions.sharp,'0.35.5');
 const buffer=await sharp({create:{width:4,height:4,channels:4,background:{r:30,g:100,b:200,alpha:1}}}).png().toBuffer();
 const output=await optimizeImage({buffer,contentType:'image/'+format,quality:75,width:2,height:2,concurrency:1,timeoutInSeconds:10});
 const meta=await sharp(output).metadata();if(format==='avif')assert.equal(output.subarray(8,12).toString(),'avif');else assert.equal(meta.format,format);assert.equal(meta.width,2);assert.equal(meta.height,2);
});
