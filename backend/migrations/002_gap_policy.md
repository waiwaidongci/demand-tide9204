# 缺口策略与逐日输入快照

`forecast_runs.gap_policy VARCHAR(20) NOT NULL DEFAULT 'strict'`：`strict` 严格拒绝日期缺口；`same_weekday` 用该日之前最近的同星期实测需求补缺。服务启动的 `create_all` 只建新表，已有部署须手工执行：

```sql
ALTER TABLE forecast_runs ADD COLUMN gap_policy VARCHAR(20) NOT NULL DEFAULT 'strict';
```

任务完成时 `forecast_runs.result.input` 固化逐日训练输入，每行含 `day`、`value`、`actual`、`source_day`。`result` 同时记录 `actual_days`、`imputed_days`、`valid_validation_days`、`missing_runs`、`actual_checksum`。已完成的运行不会被后来补录的观测改写；迟到观测只影响此后新建的任务。

历史任务默认按 `strict` 展示；它们在旧口径下没有 `input` 快照，页面与导出只显示预测点，不回填推断数据。
