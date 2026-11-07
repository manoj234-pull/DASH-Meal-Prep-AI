"""Multilabel recipe-selection metrics, using only the standard library."""
def selection_metrics(pairs, labels):
    labels = sorted(set(labels) | {x for _, p in pairs for x in p})
    def scores(tp, fp, fn):
        return {'precision': tp/(tp+fp) if tp+fp else 0.0,
                'recall': tp/(tp+fn) if tp+fn else 0.0,
                'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.0,
                'support': tp+fn, 'tp':tp, 'fp':fp, 'fn':fn}
    rows = {}
    for label in labels:
        tp=sum(label in t and label in p for t,p in pairs)
        fp=sum(label not in t and label in p for t,p in pairs)
        fn=sum(label in t and label not in p for t,p in pairs)
        rows[label]=scores(tp,fp,fn)
    support=sum(r['support'] for r in rows.values())
    macro={k:sum(r[k] for r in rows.values())/len(rows) if rows else None for k in ('precision','recall','f1')}
    weighted={k:sum(r[k]*r['support'] for r in rows.values())/support if support else None for k in ('precision','recall','f1')}
    micro=scores(*(sum(r[k] for r in rows.values()) for k in ('tp','fp','fn')))
    return {'evaluated_queries':len(pairs),
            'accuracy':sum(set(t)==set(p) for t,p in pairs)/len(pairs) if pairs else None,
            'accuracy_definition':'Exact recipe-set match per valid query; not overall application accuracy.',
            'zero_division_policy':'Undefined per-label precision/recall/F1 are 0; support-zero labels are included in macro average.',
            'per_recipe':rows, 'micro_average':micro,
            'macro_average':{**macro,'support':support},
            'weighted_average':{**weighted,'support':support}}
