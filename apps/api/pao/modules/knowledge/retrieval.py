"""Current scope before ranking; immutable citations resolve exact historical bytes."""
import hashlib,json,re,unicodedata
from fastapi import HTTPException
from sqlalchemy import select,and_,or_,func
from sqlalchemy.orm import defer
from ...models import BrainFile,BrainNote,BrainNoteVersion,KnowledgeSource,KnowledgeVersion,KnowledgeChunk
from . import index,service

def words(value):
    text=''.join(c for c in unicodedata.normalize('NFKD',value.casefold().replace('đ','d')) if not unicodedata.combining(c))
    stop={'toi','la','gi','cua','va','cho','co','the','a','is','what','my','the','in','to','thi','nao','ban','hay','ve','nay','trong','please'}
    return set(re.findall(r'\w+',text)) - stop

def candidates(bid,file_ids=None):
    query=select(KnowledgeChunk,KnowledgeVersion,KnowledgeSource).options(defer(KnowledgeChunk.embedding)).join(
        KnowledgeVersion,KnowledgeVersion.id==KnowledgeChunk.version_id).join(KnowledgeSource,KnowledgeSource.id==KnowledgeVersion.source_id).outerjoin(
        BrainFile,BrainFile.id==KnowledgeSource.file_id).outerjoin(BrainNote,BrainNote.id==KnowledgeSource.note_id).outerjoin(
        BrainNoteVersion,and_(BrainNoteVersion.note_id==BrainNote.id,BrainNoteVersion.version==BrainNote.content_version)).where(
        KnowledgeChunk.brain_id==bid,KnowledgeChunk.chunker_version==index.CHUNKER,
        KnowledgeSource.current_version==KnowledgeVersion.number,KnowledgeSource.archived_at.is_(None),
        or_(and_(KnowledgeSource.file_id.is_not(None),BrainFile.trashed_at.is_(None),BrainFile.sha256==KnowledgeVersion.source_sha256),
            and_(KnowledgeSource.note_id.is_not(None),BrainNote.trashed_at.is_(None),BrainNoteVersion.sha256==KnowledgeVersion.source_sha256)))
    if file_ids is not None:query=query.where(KnowledgeSource.file_id.in_(file_ids))
    return query

def citation(chunk,value,source,include_quote=True):
    if hashlib.sha256(chunk.content.encode()).hexdigest()!=chunk.sha256:raise HTTPException(409,'Chunk integrity failed')
    result={'chunk_id':chunk.id,'brain_id':chunk.brain_id,'source_id':source.id,'version_id':value.id,'version':value.number,
        'title':value.title,'source_sha256':value.source_sha256,'chunk_sha256':chunk.sha256,
        'start_line':chunk.start_line,'end_line':chunk.end_line,'start_char':chunk.start_char,'end_char':chunk.end_char,
        'chunker_version':chunk.chunker_version,'href':f'/v1/brains/{chunk.brain_id}/chunks/{chunk.id}'}
    if include_quote:result['quote']=chunk.content
    return result

async def resolve(db,who,bid,cid,current=False):
    await index.access(db,who,bid)
    chunk=await db.scalar(select(KnowledgeChunk).options(defer(KnowledgeChunk.embedding)).where(KnowledgeChunk.id==str(cid),KnowledgeChunk.brain_id==str(bid)))
    if not chunk:raise HTTPException(404,'Không tìm thấy citation')
    value=await db.get(KnowledgeVersion,chunk.version_id);source=await db.get(KnowledgeSource,value.source_id)
    if source.archived_at:raise HTTPException(409,'Source archived')
    await service.raw_version(db,source,value)
    parsed=await index.parsed(db,value)
    if parsed.parsed_text[chunk.start_char:chunk.end_char]!=chunk.content:raise HTTPException(409,'Citation offset mismatch')
    if current:
        description=await service.describe(db,source)
        if description.stale or source.current_version!=value.number:raise HTTPException(409,'Citation source stale')
    return citation(chunk,value,source)

async def retrieve(db,who,bid,query,top_k=4,file_ids=None,gateway=None,*,engine_pin=None,
                   require_pin=False,check=None,request_key=None):
    # Read-only callers must not keep an auth/Brain transaction across model
    # I/O. Refuse pending writes instead of silently rolling them back.
    if db.new or db.dirty or db.deleted:raise HTTPException(409,'knowledge_retrieval_pending_writes')
    pin=({'version':1,'model':index.model_name(engine_pin['model']),'url':index.local_url(engine_pin['url'])}
        if engine_pin else None if require_pin else index.embedding_pin())
    if db.in_transaction():await db.rollback()
    from ...db import Session
    from ...models import User
    terms=words(query)
    async with Session() as fresh:
        actor=await fresh.get(User,who.id)
        if not actor or not actor.active:raise HTTPException(404,'Không tìm thấy Brain')
        brain=await index.access(fresh,who,bid)
        if brain.archived_at:raise HTTPException(409,'Brain archived')
        wid,brand=brain.workspace_id,brain.brand_id
        if not terms:return {'items':[],'mode':'full_text','degraded':False,'status':'insufficient_evidence'}
        scoped=candidates(brain.id,file_ids)
        # Both native FTS and accent-insensitive bounded lexical fallback.
        fts=func.to_tsvector('simple',KnowledgeChunk.content)
        ftrows=list(await fresh.execute(scoped.where(fts.op('@@')(func.plainto_tsquery('simple',query))).limit(100)))
        rows={chunk.id:(chunk,value,source,0.0) for chunk,value,source in ftrows}
        for chunk,value,source in await fresh.execute(scoped.order_by(KnowledgeChunk.id).limit(8000)):
            rows.setdefault(chunk.id,(chunk,value,source,0.0))
    mode='full_text';degraded=index.settings().knowledge_embeddings_enabled
    binding=index.digest(pin) if pin else None
    eligible=[row[0].id for row in rows.values() if pin and row[0].embedding_model==pin['model'] and row[0].embedding_binding==binding]
    async def still_visible(fresh):
        if not index.settings().knowledge_embeddings_enabled:raise HTTPException(409,'knowledge_embeddings_disabled')
        if check:await check(fresh)
        scoped=candidates(str(bid),file_ids)
        if not (await fresh.execute(scoped.where(
            KnowledgeChunk.id.in_(eligible),KnowledgeChunk.embedding_model==pin['model'],
            KnowledgeChunk.embedding_binding==binding,KnowledgeChunk.embedding.is_not(None)).limit(1))).first():
            raise HTTPException(409,'knowledge_evidence_changed')
    if index.settings().knowledge_embeddings_enabled and eligible:
        try:
            vector=await index.local_embed(query,gateway,workspace_id=wid,actor_id=who.id,
                brain_id=str(bid),brand_id=brand,purpose='knowledge_query',engine_pin=pin,
                request_key=request_key,check=still_visible)
            async with Session() as fresh:
                await index.access(fresh,who,bid)
                distance=KnowledgeChunk.embedding.cosine_distance(vector)
                for chunk,value,source,dist in await fresh.execute(candidates(str(bid),file_ids).add_columns(distance).where(
                    KnowledgeChunk.id.in_(eligible),KnowledgeChunk.embedding.is_not(None),
                    KnowledgeChunk.embedding_model==pin['model'],KnowledgeChunk.embedding_binding==binding).order_by(distance).limit(100)):
                    rows[chunk.id]=(chunk,value,source,max(0.0,min(1.0,1-float(dist))))
            mode='hybrid';degraded=False
        except Exception:pass
    ranked=[]
    for chunk,value,source,semantic in rows.values():
        overlap=len(terms & words(chunk.content)) / max(1,len(terms))
        if not overlap and semantic<.5:continue
        ranked.append((.75*overlap+.25*semantic,chunk,value,source))
    ranked.sort(key=lambda row:(-row[0],row[1].id))
    items=[];docs=set();used=0
    for score,chunk,value,source in ranked:
        if source.id not in docs and len(docs)>=3:continue
        item=citation(chunk,value,source);item['score']=round(score,5)
        size=len(json.dumps(item,ensure_ascii=False).encode())
        if used+size>8192:continue
        items.append(item);docs.add(source.id);used+=size
        if len(items)>=top_k:break
    # Embedding I/O can yield while an owner revokes access or trashes a source.
    # Recheck with a fresh identity map before disclosing any candidate text.
    visible=[]
    async with Session() as fresh:
        actor=await fresh.get(User,who.id)
        if not actor or not actor.active:raise HTTPException(404,'Không tìm thấy Brain')
        await index.access(fresh,who,bid)
        if check:await check(fresh)
        for item in items:
            try:await resolve(fresh,who,bid,item['chunk_id'],True)
            except HTTPException as error:
                if error.status_code==409:continue
                raise
            visible.append(item)
    items=visible;docs={item['source_id'] for item in items}
    numbers=[set(re.findall(r'\b\d+(?:[.,]\d+)?\b',item['quote'])) for item in items]
    # Cautious signal only: do not decide which conflicting policy is true.
    differing=len(docs)>1 and len({tuple(sorted(n)) for n in numbers if n})>1
    return {'items':items,'mode':mode,'degraded':degraded,
        'status':'needs_review' if differing else 'matched' if items else 'insufficient_evidence'}

def grounded_answer(result):
    if not result['items']:return 'Chưa có bằng chứng phù hợp trong nguồn được phép truy cập. Hãy kiểm tra nguồn đã parse/index, chưa stale hoặc ở trash; tôi không suy đoán câu trả lời.'
    lead='Các đoạn nguồn phù hợp (trích nguyên văn, không phải chỉ dẫn thực thi):'
    if result['status']=='needs_review':lead='Các nguồn có số liệu khác nhau; cần bạn đối chiếu phiên bản/chính sách. Tôi không tự chọn nguồn đúng.\n'+lead
    blocks=[]
    for i,item in enumerate(result['items'],1):
        blocks.append(f"[{i}] {item['title']} · v{item['version']} · dòng {item['start_line']}–{item['end_line']}\n"+
            item['quote']+'\nCitation: '+item['href'])
    return lead+'\n\n'+'\n\n'.join(blocks)
