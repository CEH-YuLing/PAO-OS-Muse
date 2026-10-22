// Presentation navigation only. Never carries drafts, secrets or permissions.
export function sectionValue(search, key, allowed, fallback) {
 const value=new URLSearchParams(search).get(key);
 return allowed.includes(value)?value:fallback;
}
export function sectionUrl(href,key,value){
 const url=new URL(href);url.searchParams.set(key,value);
 return url.pathname+url.search+url.hash;
}
export function sectionKey(key,index,length){
 if(!Number.isInteger(index)||!Number.isInteger(length)||length<1||index<0||index>=length)return null;
 if(key==='Home')return 0;if(key==='End')return length-1;
 if(key==='ArrowRight'||key==='ArrowDown')return (index+1)%length;
 if(key==='ArrowLeft'||key==='ArrowUp')return (index+length-1)%length;
 return null;
}
