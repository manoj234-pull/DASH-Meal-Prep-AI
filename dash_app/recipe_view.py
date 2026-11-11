"""Reusable filtering, ordering and display limits over verified recipe rows."""
import math
import operator
import re

FIELDS={'match_percent','pantry_match_percent','sodium_mg_per_serving','vegetarian','missing_count'}
OPS={'eq':operator.eq,'ne':operator.ne,'gt':operator.gt,'gte':operator.ge,'lt':operator.lt,'lte':operator.le}
DEFAULT_VIEW={'filters':[],'sort_by':None,'direction':'desc','limit':None,
              'include_ingredients':[],'exclude_ingredients':[],'exclude_recipe_ids':[],'title_contains':''}

def ingredient_tokens(value):
    return [word[:-1] if len(word)>3 and word.endswith('s') and not word.endswith(('ss','us','is')) else word
            for word in re.findall(r"[a-z0-9]+",str(value).casefold())]

def ingredient_name_matches(name, requested):
    name_words=ingredient_tokens(name); requested_words=ingredient_tokens(requested)
    return bool(requested_words) and any(name_words[i:i+len(requested_words)]==requested_words
                                         for i in range(len(name_words)-len(requested_words)+1))

def recipe_term_matches(row, requested):
    return ingredient_name_matches(row.get('title',''),requested) or any(
        ingredient_name_matches(item.get('name',''),requested) for item in row.get('ingredients',[]))

def validate_view(previous,patch):
    if not isinstance(patch,dict) or not set(patch).issubset(DEFAULT_VIEW):raise ValueError('Unsupported result option')
    view={**DEFAULT_VIEW,**previous,**patch}
    if (view['sort_by'] is not None and view['sort_by'] not in FIELDS) or view['direction'] not in ('asc','desc'):raise ValueError('Unsupported sorting option')
    n=view['limit']
    if n is not None and (isinstance(n,bool) or not isinstance(n,int) or not 1<=n<=100):raise ValueError('Choose 1–100 results or no limit')
    filters=view['filters']
    if not isinstance(filters,list) or len(filters)>12:raise ValueError('Too many conditions')
    for condition in filters:
        if not isinstance(condition,dict) or set(condition)!={'field','operator','value'}:raise ValueError('Invalid condition')
        field,op,value=condition['field'],condition['operator'],condition['value']
        if not isinstance(field,str) or field not in FIELDS or not isinstance(op,str) or op not in OPS:raise ValueError('Unsupported condition')
        if field=='vegetarian':
            if not isinstance(value,bool) or op not in ('eq','ne'):raise ValueError('Vegetarian condition needs true or false')
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('Condition needs a non-negative number')
        elif field in ('match_percent','pantry_match_percent') and value>100:raise ValueError('Match cannot exceed 100 percent')
    for field in ('include_ingredients','exclude_ingredients'):
        terms=view[field]
        if (not isinstance(terms,list) or len(terms)>20 or
                any(not isinstance(name,str) or not name.strip() or len(name)>100 for name in terms)):
            raise ValueError('Use up to 20 recipe or ingredient terms')
        view[field]=[name.strip().casefold() for name in terms]
    ids=view['exclude_recipe_ids']
    if (not isinstance(ids,list) or len(ids)>100 or
            any(not isinstance(recipe_id,str) or not recipe_id.strip() or len(recipe_id)>100 for recipe_id in ids)):
        raise ValueError('Use up to 100 recipe IDs')
    view['exclude_recipe_ids']=[recipe_id.strip() for recipe_id in ids]
    title=view['title_contains']
    if not isinstance(title,str) or len(title)>100:raise ValueError('Use a short recipe title filter')
    view['title_contains']=title.strip().casefold()
    return view

def value_of(row,field):
    return len(row['missing']) if field=='missing_count' else row.get(field)

def apply_view(rows,view):
    view=validate_view({},view)
    matches=[row for row in rows if all(value_of(row,c['field']) is not None and OPS[c['operator']](value_of(row,c['field']),c['value']) for c in view['filters'])
             and all(recipe_term_matches(row,wanted) for wanted in view['include_ingredients'])
             and not any(recipe_term_matches(row,unwanted) for unwanted in view['exclude_ingredients'])
             and row.get('id') not in view['exclude_recipe_ids']
             and (not view['title_contains'] or ingredient_name_matches(row.get('title',''),view['title_contains']))]
    field=view['sort_by']
    if field is None:return list(matches[:view['limit']] if view['limit'] else matches),len(matches)
    known=[r for r in matches if value_of(r,field) is not None];unknown=[r for r in matches if value_of(r,field) is None]
    known.sort(key=lambda r:r['id']);known.sort(key=lambda r:value_of(r,field),reverse=view['direction']=='desc')
    ordered=known+sorted(unknown,key=lambda r:r['id'])
    return ordered[:view['limit']] if view['limit'] else ordered,len(matches)
