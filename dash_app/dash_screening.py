"""Transparent application screening; not an official per-recipe DASH certification."""
import json,math
from .core import ROOT,preparation_complete

def screen(recipe):
 policy=json.loads((ROOT/'data/dash_screening_policy.json').read_text())
 held=[];excluded=[];review=recipe.get('source_review',{})
 if not preparation_complete(recipe):held.append('Incomplete quantities, servings or cooking instructions')
 if review.get('complete') is not True or review.get('evidence_supported') is not True:held.append('Source completeness or factual support not verified')
 sodium=recipe.get('sodium_mg_per_serving');fat=recipe.get('nutrition_per_serving',{}).get('saturated_fat_g',{}).get('value')
 for value,maximum,label in [(sodium,policy['max_sodium_mg_per_source_serving'],'Sodium'),(fat,policy['max_saturated_fat_g_per_source_serving'],'Saturated fat')]:
  if type(value) not in (float,int) or not math.isfinite(value) or value<0:held.append(label+' missing or invalid')
  elif value>maximum:excluded.append(label+' exceeds the application screening limit')
 if review.get('ingredients_suitable') is False:excluded.append(review.get('reason','Ingredients do not fit the conservative shortlist'))
 elif review.get('ingredients_suitable') is not True:held.append('Ingredient suitability uncertain')
 return {'status':'held' if held else ('excluded' if excluded else 'qualified'),'reasons':held+excluded,'policy_version':policy['version'],'scope':'Recipe screening only; not whole-day DASH compliance or clinical approval'}

def check_source_facts(recipe,text):
 import re
 from .ingestion import quantity,normalized
 issues=[];text=normalized(text)
 for item in recipe['ingredients']:
  tokens=item.get('evidence','').split();first=quantity(tokens[0]) if tokens else None
  if len(tokens)>1 and '/' in tokens[1] and quantity(tokens[1]) is not None:first=quantity(' '.join(tokens[:2]))
  if first is None or first!=item.get('quantity'):issues.append('Ingredient quantity differs from its source line')
 for label,value in [('Sodium',recipe.get('sodium_mg_per_serving')),('Saturated Fat',recipe.get('nutrition_per_serving',{}).get('saturated_fat_g',{}).get('value'))]:
  values={float(x) for x in re.findall(re.escape(label)+r'\s*:?\s*(\d+(?:\.\d+)?)\s*(?:mg|g)\b',text,re.I)}
  if len(values)!=1 or value not in values:issues.append(label+' does not have one matching source value')
 yields={float(x) for x in re.findall(r'(?:makes|yield)\s*:?\s*(\d+(?:\.\d+)?)\s+servings?',text,re.I)}
 if yields!={recipe['base_servings']}:issues.append('Serving count does not match the source yield')
 return list(dict.fromkeys(issues))
