from typing import Literal
from pydantic import BaseModel,Field
class RunInput(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    series_id:int=Field(gt=0)
    horizon:int=Field(default=14,ge=1,le=30)
    season:int=Field(default=7,ge=2,le=30)
    gap_policy:Literal['strict','same_weekday']=Field(
        default='strict',
        description='strict=日期缺口直接失败；same_weekday=用此前最近的同星期实测需求补缺，连续缺失不得超过7天',
    )
