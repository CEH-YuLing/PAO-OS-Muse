"""Public model/effort metadata, never identity, entitlement or inference proof."""
import re

def model_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]{0,119}',value):
        raise ValueError('ai_model_invalid')
    return value

def normalize(rows):
    if not isinstance(rows,list) or not 1<=len(rows)<=500:raise ValueError('ai_catalog_invalid')
    result=[];seen=set()
    for row in rows:
        if isinstance(row,str):row={'model':row}
        if not isinstance(row,dict):raise ValueError('ai_catalog_invalid')
        name=model_id(row.get('model'))
        if name in seen:raise ValueError('ai_catalog_invalid')
        seen.add(name)
        label=row.get('display_name',name)
        if not isinstance(label,str) or not 1<=len(label)<=160 or any(ord(c)<32 for c in label):raise ValueError('ai_catalog_invalid')
        efforts=row.get('reasoning_efforts',[])
        if (not isinstance(efforts,list) or len(efforts)>12
                or any(not isinstance(v,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,23}',v) for v in efforts)
                or len(set(efforts))!=len(efforts)):
            raise ValueError('ai_catalog_invalid')
        default=row.get('default_effort')
        if default is not None and default not in efforts:raise ValueError('ai_catalog_invalid')
        item={'model':name,'display_name':label,'reasoning_efforts':list(efforts),
              'default_effort':default,'availability':'catalog_only'}
        if 'provider_output_modalities' in row:
            from .modalities import outputs
            item['provider_output_modalities']=outputs(row['provider_output_modalities'])
        result.append(item)
    return result

def selection(catalog,model,effort=None):
    name=model_id(model)
    row=next((v for v in normalize(catalog) if v['model']==name),None)
    if row is None:raise ValueError('ai_model_not_in_catalog')
    if effort is not None and effort not in row['reasoning_efforts']:raise ValueError('ai_effort_not_supported')
    return {'model':name,'reasoning_effort':effort}
