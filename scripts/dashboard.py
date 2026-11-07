from html import escape

def dashboard(report):
    m=report['recipe_selection_metrics']; pct=lambda x: 'Not measured' if x is None else f'{100*x:.1f}%'
    rows=''
    for name,values in [('Micro average',m['micro_average']),('Macro average',m['macro_average']),('Weighted average',m['weighted_average'])]:
        rows+=f"<tr><td>{name}</td><td>{pct(m['accuracy']) if name=='Micro average' else '—'}</td><td>{pct(values['precision'])}</td><td>{pct(values['recall'])}</td><td>{pct(values['f1'])}</td><td>{values['support']}</td></tr>"
    labels=''
    support=m['weighted_average']['support']
    for name,v in m['per_recipe'].items():
        labels+=f"<tr><td>{escape(name)}</td><td>{v['support']}</td><td>{pct(v['support']/support if support else None)}</td><td>{pct(v['precision'])}</td><td>{pct(v['recall'])}</td><td>{pct(v['f1'])}</td></tr>"
    def bars(items):
        return ''.join(f'<div class="barrow"><span>{escape(name)}</span><div class="track"><div class="bar" style="width:{value}%"></div></div><b>{value:.1f}%</b></div>' for name,value in items)
    names={'happy_path':'Common inputs','edge_case':'Edge / unknown inputs','known_failure':'Known matching problems','adversarial':'Malformed inputs'}
    breakdown=''.join(f"<tr><td>{names.get(k,k)}</td><td>{v['passed']} / {v['evaluated']}</td><td>{v['evaluated']-v['passed']}</td><td>{v['pass_percent']:.1f}%</td></tr>" for k,v in report['by_category'].items())
    failed='; '.join(c['description'] for c in report['cases'] if not c['passed'])
    mix=[(names.get(k,k),100*v['evaluated']/report['evaluated']) for k,v in report['by_category'].items()]
    rates=[(names.get(k,k)+f" ({v['passed']}/{v['evaluated']})",v['pass_percent']) for k,v in report['by_category'].items()]
    cases=''.join(f"<tr><td>{c['id']}</td><td>{escape(c['category'])}</td><td>{escape(c['description'])}</td><td>{'PASS' if c['passed'] else 'FAIL'}</td><td>{escape('; '.join(c['errors']))}</td></tr>" for c in report['cases'])
    return f"""<!doctype html><html><head><meta charset='utf-8'><style>
    body{{font:14px/1.5 system-ui;color:#18352c;margin:20px;background:#fff}}h2,h3{{margin-bottom:8px}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #dce6df}}.barrow{{display:grid;grid-template-columns:minmax(140px,240px) 1fr 65px;gap:8px;align-items:center;margin:10px 0}}.track{{height:20px;background:#edf1ed;border-radius:4px;overflow:hidden}}.bar{{height:100%;background:#28765b}}.note{{padding:12px;background:#fff5df}}details{{margin-top:16px}}small{{color:#64736b}}</style></head><body>
    <h2>Evaluation dashboard</h2><p>{report['passed']}/{report['evaluated']} checks passed ({report['pass_percent']}%). <b>Local recipe logic only.</b></p>
    <p class='note'>Scenario mix is not a forced score. A correct rejection passes. Golden labels are assistant-authored and need human review. Live LLM faithfulness and retrieval relevance are not measured by these metrics.</p>
    <h3>Why the overall result is {report['pass_percent']}%</h3><table><tr><th>Type of test</th><th>Passed / tested</th><th>Failed</th><th>Pass rate in this group</th></tr>{breakdown}<tr><th>Total</th><th>{report['passed']} / {report['evaluated']}</th><th>{report['evaluated']-report['passed']}</th><th>{report['pass_percent']}%</th></tr></table><p>Each group has its own percentage. We add the passing cases, not the group percentages. Correctly rejecting an invalid request counts as passing.</p><p><strong>Observed problems:</strong> {escape(failed) if failed else 'None in this saved run.'}</p><details><summary>Charts: dataset mix and actual pass rates</summary><h3>Dataset composition (coverage, not accuracy)</h3>{bars(mix)}<h3>Actual pass rate by scenario</h3>{bars(rates)}</details>
    <h3>Recipe-selection metrics</h3><table><tr><th>Average</th><th>Exact-set accuracy</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr>{rows}</table>
    <p>Accuracy uses {m['evaluated_queries']} valid queries. Invalid-input checks remain in the overall pass rate. Support counts expected recipe occurrences, not the 20 scenarios.</p>
    <p>Precision: returned recipes that were correct. Recall: expected recipes found. F1 balances both. Micro pools decisions; macro gives all catalog recipes equal weight. Weighted average = sum of (each recipe's metric × its support) ÷ total support. The 50/30/15/5 scenario percentages are <b>not</b> these weights.</p>
    <details><summary>Recipe classes and their actual weights</summary><table><tr><th>Recipe ID</th><th>Support</th><th>Weight</th><th>Precision</th><th>Recall</th><th>F1</th></tr>{labels}</table><p>{escape(m['zero_division_policy'])}</p></details>
    <details><summary>All 20 scenarios and actual outcomes</summary><table><tr><th>ID</th><th>Category</th><th>Scenario</th><th>Result</th><th>Failures</th></tr>{cases}</table></details>
    <small>Run: {report['timestamp']} · Dataset SHA: {report['golden_sha256'][:12]}</small></body></html>"""
