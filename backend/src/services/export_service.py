import io,csv
from fastapi import HTTPException
from .run_service import detail

INPUT_HEADERS=['序列','记录类型','日期','数值','数据性质','来源日期','经验下界','经验上界','模型','口径说明']
POLICY_LABELS={'strict':'严格拒绝缺口','same_weekday':'按此前同星期需求补缺'}

def export_csv(db,run_id):
    run=detail(db,run_id)
    if run['status']!='completed': raise HTTPException(409,'预测尚未完成')
    result=run['result'] or {}
    policy=POLICY_LABELS.get(run.get('gap_policy'),run.get('gap_policy') or '严格拒绝缺口')
    note=result.get('interval_note','')
    if not result.get('input'):
        note=f'{note}本任务早于逐日输入快照版本，未记录训练输入明细。'.strip()
    stream=io.StringIO(); stream.write('﻿')
    writer=csv.writer(stream)
    writer.writerow(INPUT_HEADERS)
    for row in result.get('input',[]):
        actual=row.get('actual')
        writer.writerow([
            run['series']['name'],'训练输入',row['day'],row['value'],
            '实测' if actual else '同周补值',
            row.get('source_day') or '',
            '','','',note if actual else f'按此前同星期实测补缺；来源日期 {row.get("source_day")}；{policy}',
        ])
    for p in run['points']:
        writer.writerow([
            run['series']['name'],'未来预测',p['day'],p['predicted'],'预测','',
            p['lower'],p['upper'],result.get('selected',{}).get('model',''),note,
        ])
    return stream.getvalue()
