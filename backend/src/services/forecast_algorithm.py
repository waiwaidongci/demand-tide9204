"""Deterministic one-step rolling validation; each fit sees only earlier observations.

Missing calendar days can either be rejected (``strict``) or reconstructed from the
most recent *observed* value on the same weekday before that day (``same_weekday``).
Reconstruction is causal by construction: a missing day only ever reads an actual
observation from an earlier day, never a later observation or another imputed value.
Imputed days are also excluded from backtest ground truth, and every candidate is
scored on the exact same set of actually observed validation days.
"""
import math
from datetime import date,timedelta
from statistics import mean

GAP_POLICY_STRICT='strict'
GAP_POLICY_SAME_WEEKDAY='same_weekday'
GAP_POLICIES=(GAP_POLICY_STRICT,GAP_POLICY_SAME_WEEKDAY)
MAX_CONSECUTIVE_MISSING_DAYS=7
MIN_VALIDATION_ACTUAL_DAYS=7

def quantile(values,p):
    values=sorted(values)
    pos=(len(values)-1)*p
    lo=int(pos); hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(pos-lo)

def predict(history,model,season,alpha=.5):
    if model=='seasonal_naive': return history[-season]
    level=history[0]
    for value in history[1:]: level=alpha*value+(1-alpha)*level
    return level

def _normalise(observations):
    rows=[]
    for day,value in observations:
        if not isinstance(day,date): raise ValueError('观测日期格式无效')
        try: value=float(value)
        except (TypeError,ValueError): raise ValueError('需求必须为非负有限数')
        rows.append((day,value))
    rows.sort(key=lambda row:row[0])
    if any(a[0]==b[0] for a,b in zip(rows,rows[1:])): raise ValueError('观测日期重复，请核对后重试')
    return rows

def _missing_runs(start,end,actual):
    """Maximal runs of calendar days with no observation, as (start,end,days)."""
    runs=[]; run_start=None; day=start
    while day<=end:
        if day not in actual:
            if run_start is None: run_start=day
        elif run_start is not None:
            runs.append((run_start,day-timedelta(days=1),(day-run_start).days))
            run_start=None
        day+=timedelta(days=1)
    if run_start is not None:
        runs.append((run_start,end,(end-run_start).days+1))
    return runs

def _build_timeline(rows,policy):
    """Return one row per calendar day plus the list of missing runs.

    A timelime row is ``{day,value,actual,source_day}``. For a strict timeline every
    row is actual. For a same-weekday timeline a missing day is filled from the most
    recent actual observation exactly 7, 14, ... days earlier.
    """
    start,end=rows[0][0],rows[-1][0]
    actual=dict(rows)
    span=(end-start).days+1
    if policy==GAP_POLICY_STRICT:
        missing=[day for day in (start+timedelta(days=i) for i in range(span)) if day not in actual]
        if missing:
            raise ValueError(
                f'序列日期不连续，请补齐缺失日再预测：{missing[0].isoformat()} 起共缺 {len(missing)} 天。'
                '若希望按此前同星期实测需求补缺，请把任务缺口策略改为 same_weekday 后重建。'
            )
        return [{'day':day,'value':actual[day],'actual':True,'source_day':None}
                for day in (start+timedelta(days=i) for i in range(span))],[]

    if policy not in GAP_POLICIES: raise ValueError('不支持的缺口策略')
    runs=_missing_runs(start,end,actual)
    too_long=[run for run in runs if run[2]>MAX_CONSECUTIVE_MISSING_DAYS]
    if too_long:
        detail='；'.join(f'{a.isoformat()} 至 {b.isoformat()} 共 {n} 天' for a,b,n in too_long)
        raise ValueError(
            f'连续缺失过长：{detail}。同周补缺最多允许连续缺失 {MAX_CONSECUTIVE_MISSING_DAYS} 天，'
            '请先补齐这些日期的观测，或核对数据是否完整。'
        )

    timeline=[]; unfillable=[]
    for offset in range(span):
        day=start+timedelta(days=offset)
        if day in actual:
            timeline.append({'day':day,'value':actual[day],'actual':True,'source_day':None})
            continue
        source=day-timedelta(days=7)
        while source>=start and source not in actual: source-=timedelta(days=7)
        if source<start:
            unfillable.append(day); continue
        timeline.append({'day':day,'value':actual[source],'actual':False,'source_day':source})
    if unfillable:
        detail='、'.join(day.isoformat() for day in unfillable[:5])
        suffix='等' if len(unfillable)>5 else ''
        raise ValueError(
            f'无法按同周补缺：{detail}{suffix} 之前没有同星期的实测记录。'
            '请补齐更早的观测，或改用严格拒绝策略并处理缺口。'
        )
    return timeline,runs

def forecast_observations(observations,horizon,season,gap_policy=GAP_POLICY_STRICT):
    """Forecast from ``(day,value)`` observations, optionally filling calendar gaps.

    The rolling validation only scores days that were actually observed. Filled days
    remain in the model history (so recursive forecasts have a continuous series) but
    never contribute an error term; therefore all candidates use identical valid dates.
    """
    if not 1<=horizon<=30 or not 2<=season<=30: raise ValueError('预测期1–30天，季节周期2–30天')
    if gap_policy not in GAP_POLICIES: raise ValueError('不支持的缺口策略')
    rows=_normalise(observations)
    if not rows: raise ValueError('观测不足：至少42天且不少于3个季节周期')
    timeline,missing_runs=_build_timeline(rows,gap_policy)
    span=len(timeline)
    if span<max(42,season*3): raise ValueError('观测不足：至少42天且不少于3个季节周期')
    if any(not math.isfinite(row['value']) or row['value']<0 for row in timeline):
        raise ValueError('需求必须为非负有限数')

    actual_days=sum(1 for row in timeline if row['actual'])
    imputed_days=span-actual_days
    if gap_policy==GAP_POLICY_SAME_WEEKDAY and actual_days<max(42,season*3):
        raise ValueError(
            f'有效实测样本不足：连续日期 {span} 天中实测 {actual_days} 天，'
            f'至少需要 {max(42,season*3)} 天。请补齐更多观测后再运行预测。'
        )

    values=[row['value'] for row in timeline]
    holdout=min(28,span//3)
    validation_start=span-holdout
    # Missing days are not ground truth. All candidates are judged on this same list.
    valid_indices=[i for i in range(validation_start,span) if timeline[i]['actual']]
    if len(valid_indices)<MIN_VALIDATION_ACTUAL_DAYS:
        raise ValueError(
            f'有效验证样本不足：留出的 {holdout} 天中仅 {len(valid_indices)} 天为实测，'
            f'至少需要 {MIN_VALIDATION_ACTUAL_DAYS} 天。请补齐近期观测后再运行预测。'
        )

    candidates=[('seasonal_naive',None),('exponential_smoothing',.2),('exponential_smoothing',.5),('exponential_smoothing',.8)]
    comparisons=[]; residual_sets=[]
    for model,alpha in candidates:
        predictions=[predict(values[:i],model,season,alpha) for i in valid_indices]
        residuals=[values[i]-p for i,p in zip(valid_indices,predictions)]
        mae=mean(abs(e) for e in residuals)
        denom=sum(values[i] for i in valid_indices)
        comparisons.append({'model':model,'alpha':alpha,'mae':round(mae,4),
                            'wape':round(sum(abs(e) for e in residuals)/denom,6) if denom else None})
        residual_sets.append(residuals)
    best=min(range(len(comparisons)),key=lambda i:comparisons[i]['mae'])
    selected=comparisons[best]
    residuals=residual_sets[best]
    low,high=quantile(residuals,.1),quantile(residuals,.9)
    history=list(values)
    points=[]
    for _ in range(horizon):
        point=predict(history,selected['model'],season,selected['alpha'])
        history.append(point)
        points.append({'predicted':round(point,2),'lower':round(max(0,point+low),2),'upper':round(max(0,point+high),2)})
    actual_checksum=round(sum(row['value'] for row in timeline if row['actual']),4)
    return {
        'selected':selected,'comparisons':comparisons,
        'validation_days':holdout,'valid_validation_days':len(valid_indices),
        'training_days':span,'actual_days':actual_days,'imputed_days':imputed_days,
        'gap_policy':gap_policy,
        'missing_runs':[{'start':a.isoformat(),'end':b.isoformat(),'days':n} for a,b,n in missing_runs],
        'input':[{'day':row['day'].isoformat(),'value':row['value'],
                  'actual':row['actual'],
                  'source_day':row['source_day'].isoformat() if row['source_day'] else None}
                 for row in timeline],
        'interval_note':'滚动回测残差的10%/90%经验分位带；未来覆盖率没有保证，未建模节假日冲击。',
        'points':points,
        'checksum':round(sum(values),4),
        'actual_checksum':actual_checksum,
    }

def forecast(values,horizon,season):
    """Backward-compatible wrapper for an already contiguous series."""
    start=date(2000,1,1)
    observations=[(start+timedelta(days=i),value) for i,value in enumerate(values)]
    return forecast_observations(observations,horizon,season,GAP_POLICY_STRICT)
