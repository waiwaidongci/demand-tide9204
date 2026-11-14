export const number=(v:number|undefined)=>v===undefined?'—':new Intl.NumberFormat('zh-CN',{maximumFractionDigits:2}).format(v);
export const modelName=(m:string|undefined)=>m==='seasonal_naive'?'季节朴素法':m==='exponential_smoothing'?'指数平滑':'等待回测';
export const dateTime=(v:string)=>v.replace('T',' ').slice(0,16)+' UTC';

export const gapPolicyName=(v:string|undefined)=>v==='same_weekday'?'同周补缺':'严格拒绝';
export const inputKindName=(actual:boolean)=>actual?'实测':'同周补值';
