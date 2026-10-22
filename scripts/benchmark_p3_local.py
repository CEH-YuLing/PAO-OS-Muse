"""Synthetic paired context benchmark. Local-only, no DB content or cloud.

Small correctness corpus, not a claim of universal quality/performance gains.
Keep all prompts/results synthetic; output only metrics, not model reasoning.
"""
import asyncio,json,time
from pao.config import ROOT,settings
from pao.gateway import OllamaGateway
from pao.modules.engines.service import local_url
from pao.modules.chat.context import compile_messages,estimate
from pao.modules.chat.ledger import counts

async def main():
    config=settings();config.chat_features_enabled=True
    gateway=OllamaGateway(model=config.ollama_model,url=local_url())
    metrics=[]
    for fact,question,expected in [('Synthetic approved budget is 250. No spending permission.',
        'What is the approved budget? Reply only the number.','250'),
        ('Synthetic project name is PAO-ACOS.', 'What is the project name? Reply only that exact name.','PAO-ACOS')]:
        messages=[{'role':'system','content':'Read the supplied synthetic fact and answer exactly. Do not execute anything.'}]
        for index in range(12):messages.append({'role':'user' if index%2==0 else 'assistant',
            'content':f'Synthetic irrelevant note {index}: '+('This is an unrelated placeholder without a project fact. '*4)})
        messages += [{'role':'user','content':fact},{'role':'assistant','content':'Noted; no actions authorized.'},{'role':'user','content':question}]
        compiled=compile_messages(messages,max_tokens=600,max_bytes=1800)
        assert any(row['content']==fact for row in compiled.messages)
        paired=[]
        for variant,rows in [('before',messages),('after',compiled.messages)]:
            began=time.monotonic();first=None;result='';usage={}
            async with asyncio.timeout(90):
                async for chunk in gateway.stream(rows,max_tokens=32):
                    if chunk.text:
                        if first is None:first=int((time.monotonic()-began)*1000)
                        result+=chunk.text
                    if chunk.usage:usage.update(chunk.usage)
            inp,out=counts(usage);size,tokens=estimate(rows)
            correct=result.strip().strip('`". ')==expected
            paired.append({'variant':variant,'ttft_ms':first,'elapsed_ms':int((time.monotonic()-began)*1000),
                'context_bytes':size,'estimated_context_tokens':tokens,'reported_input_tokens':inp,'reported_output_tokens':out,
                'queue_wait_ms':0,'queue_wait_basis':'serial idle benchmark; no task queue', 'correct':correct})
            print(json.dumps({'case':len(metrics)+1,'model':config.ollama_model,**paired[-1]}),flush=True)
        metrics.append(paired)
    passed=all(row['correct'] for pair in metrics for row in pair) and all(pair[1]['context_bytes']<pair[0]['context_bytes'] for pair in metrics)
    report={'pass':passed,'model':config.ollama_model,'provider':'ollama','synthetic_only':True,'database_content_read':False,
        'cloud_calls':0,'corpus_size':2,'paired':metrics,'limitations':'Heuristic estimate, two synthetic recall cases only; sequential warm-cache latency is not a statistically controlled speed claim.'}
    path=ROOT/'.runtime/p3-context-benchmark.json';path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'pass':passed,'report':str(path)}))
    if not passed:raise SystemExit('P3 benchmark correctness gate not met')
if __name__=='__main__':asyncio.run(main())
