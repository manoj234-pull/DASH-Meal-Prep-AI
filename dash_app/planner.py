"""Validated weekly plans built from source-backed recipe records."""
import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
from .core import ROOT,DATA,canonical,get_recipe_details,scale_recipe,preparation_complete

PLAN_DB=DATA/'meal_plans.sqlite'

def _number(value,label,minimum,maximum):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(label)
    return value

def build_plan(payload):
    if not isinstance(payload,dict) or not set(payload).issubset({'name','entries','sodium_target_mg'}):raise ValueError('Invalid plan')
    name=payload.get('name','Weekly meal prep')
    if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Use a short plan name')
    entries=payload.get('entries')
    if not isinstance(entries,list) or not 1<=len(entries)<=35:raise ValueError('Choose 1–35 meal slots')
    target=payload.get('sodium_target_mg')
    if target is not None:_number(target,'Sodium target must be 0–5,000 mg',0,5000)
    result=[];slots=set()
    for item in entries:
        if not isinstance(item,dict) or set(item)!={'day','meal','recipe_id','servings'}:raise ValueError('Invalid meal slot')
        day=item['day'];meal=item['meal'];recipe_id=item['recipe_id'];servings=item['servings']
        if not isinstance(day,str) or not day.strip() or len(day)>30:raise ValueError('Use a short day label')
        if not isinstance(meal,str) or not meal.strip() or len(meal)>40:raise ValueError('Use a short meal label')
        if not isinstance(recipe_id,str) or len(recipe_id)>100:raise ValueError('Invalid recipe ID')
        _number(servings,'Servings must be 1–50',1,50)
        if not float(servings).is_integer():raise ValueError('Servings must be whole numbers')
        slot=(canonical(day),canonical(meal))
        if slot in slots:raise ValueError('Each day and meal slot can contain only one recipe')
        slots.add(slot);recipe=get_recipe_details(recipe_id)
        if not preparation_complete(recipe):raise ValueError('Recipe preparation data is incomplete')
        result.append({'day':day.strip(),'meal':meal.strip(),'recipe_id':recipe_id,'title':recipe['title'],
                       'servings':int(servings),'base_servings':recipe['base_servings'],'source_url':recipe['source_url'],
                       'sodium_mg_per_serving':recipe.get('sodium_mg_per_serving'),'steps':recipe['steps'],
                       'scaled_ingredients':scale_recipe(recipe,int(servings))})
    return {'name':name.strip(),'sodium_target_mg':target,'entries':result}

def build_grocery_list(plan):
    totals={}
    for entry in plan['entries']:
        for item in entry['scaled_ingredients']:
            key=(canonical(item['name']),str(item['unit']).strip())
            row=totals.setdefault(key,{'name':key[0],'unit':key[1],'quantity':0.0,'quantity_known':True,'recipes':[]})
            if item['quantity'] is None:row['quantity_known']=False
            elif row['quantity_known']:row['quantity']+=item['quantity']
            if entry['title'] not in row['recipes']:row['recipes'].append(entry['title'])
    rows=[]
    for row in totals.values():
        row['quantity']=round(row['quantity'],4) if row['quantity_known'] else None
        rows.append(row)
    return sorted(rows,key=lambda row:(row['name'],row['unit']))

def plan_nutrition_summary(plan):
    days={};target=plan.get('sodium_target_mg')
    for entry in plan['entries']:
        day=days.setdefault(entry['day'],{'sodium_mg':0.0,'meals_with_sodium':0,'meals_missing_sodium':0})
        sodium=entry.get('sodium_mg_per_serving')
        if sodium is None:day['meals_missing_sodium']+=1
        else:day['sodium_mg']+=sodium;day['meals_with_sodium']+=1
    for day in days.values():
        day['sodium_mg']=round(day['sodium_mg'],2)
        day['selected_target_mg']=target
        day['within_selected_target']=None if target is None or day['meals_missing_sodium'] else day['sodium_mg']<=target
    return {'days':days,'scope':'Source sodium per recipe serving; missing nutrition stays unknown.'}

def validate_prep_timeline(plan,tasks):
    if not isinstance(tasks,list) or len(tasks)>100:raise ValueError('Invalid preparation timeline')
    recipes={entry['recipe_id']:entry for entry in plan['entries']};result=[]
    for task in tasks:
        if not isinstance(task,dict) or set(task)!={'title','sources'}:raise ValueError('Invalid preparation task')
        title=task['title'];sources=task['sources']
        if not isinstance(title,str) or not title.strip() or len(title)>160:raise ValueError('Use a short preparation task')
        if not isinstance(sources,list) or not sources:raise ValueError('Each task needs source steps')
        texts=[]
        for source in sources:
            if not isinstance(source,dict) or set(source)!={'recipe_id','step_number'}:raise ValueError('Invalid preparation source')
            entry=recipes.get(source['recipe_id']);number=source['step_number']
            if not entry or isinstance(number,bool) or not isinstance(number,int) or not 1<=number<=len(entry['steps']):raise ValueError('Unknown recipe step')
            texts.append(entry['steps'][number-1])
        result.append({'title':title.strip(),'sources':sources,'source_texts':texts})
    return result

def _schema(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS meal_plans(plan_id TEXT PRIMARY KEY,created_utc TEXT,updated_utc TEXT,record TEXT)')
    columns={row[1] for row in connection.execute('PRAGMA table_info(meal_plans)')}
    for name,definition in [('profile_id',"TEXT NOT NULL DEFAULT 'local'"),('status',"TEXT NOT NULL DEFAULT 'draft'"),('name',"TEXT NOT NULL DEFAULT ''")]:
        if name not in columns:connection.execute(f'ALTER TABLE meal_plans ADD COLUMN {name} {definition}')

def save_plan(plan,status='draft',profile_id='local',database=PLAN_DB):
    if status not in ('draft','finalized'):raise ValueError('Invalid plan status')
    if not isinstance(profile_id,str) or not profile_id.strip() or len(profile_id)>100:raise ValueError('Invalid profile')
    plan_id=plan.get('plan_id') or str(uuid4());now=datetime.now(timezone.utc).isoformat()
    Path(database).parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(database)) as connection,connection:
        _schema(connection);old=connection.execute('SELECT created_utc,profile_id FROM meal_plans WHERE plan_id=?',(plan_id,)).fetchone()
        if old and old[1]!=profile_id:raise ValueError('Saved plan not found')
        created=old[0] if old else now
        record={**plan,'plan_id':plan_id,'profile_id':profile_id,'status':status,'created_utc':created,'updated_utc':now}
        connection.execute('INSERT OR REPLACE INTO meal_plans(plan_id,created_utc,updated_utc,record,profile_id,status,name) VALUES (?,?,?,?,?,?,?)',
                           (plan_id,created,now,json.dumps(record),profile_id,status,record.get('name','')))
    return record

def load_plan(plan_id,profile_id='local',database=PLAN_DB):
    if not isinstance(plan_id,str) or len(plan_id)>100:raise ValueError('Invalid plan ID')
    with closing(sqlite3.connect(database)) as connection:
        _schema(connection);row=connection.execute('SELECT record FROM meal_plans WHERE plan_id=? AND profile_id=?',(plan_id,profile_id)).fetchone()
    if not row:raise ValueError('Saved plan not found')
    return json.loads(row[0])

def list_plans(profile_id='local',database=PLAN_DB):
    with closing(sqlite3.connect(database)) as connection:
        _schema(connection)
        rows=connection.execute('SELECT record FROM meal_plans WHERE profile_id=? ORDER BY updated_utc DESC, rowid DESC',(profile_id,)).fetchall()
    return [json.loads(row[0]) for row in rows]

def duplicate_plan(plan_id,profile_id='local',database=PLAN_DB):
    original=load_plan(plan_id,profile_id,database)
    copy={k:v for k,v in original.items() if k not in ('plan_id','created_utc','updated_utc','profile_id','status')}
    copy['name']='Copy of '+original.get('name','Weekly meal prep')
    return save_plan(copy,'draft',profile_id,database)

def rename_plan(plan_id,name,profile_id='local',database=PLAN_DB):
    if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Use a short plan name')
    plan=load_plan(plan_id,profile_id,database);plan['name']=name.strip()
    return save_plan(plan,plan.get('status','draft'),profile_id,database)

def delete_plan(plan_id,profile_id='local',database=PLAN_DB):
    with closing(sqlite3.connect(database)) as connection,connection:
        _schema(connection);cursor=connection.execute('DELETE FROM meal_plans WHERE plan_id=? AND profile_id=?',(plan_id,profile_id))
        if cursor.rowcount!=1:raise ValueError('Saved plan not found')
