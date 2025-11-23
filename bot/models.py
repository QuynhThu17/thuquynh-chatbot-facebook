"""
Pydantic Models cho Bot Module
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class BotResponse(BaseModel):
    response: str = Field(description="Bot's response message")
    segments: Optional[List[Dict[str, Union[str, List[str]]]]] = Field(
        description="Response segments with type and data", 
        default=None
    )
    metadata: Optional[Dict[str, Any]] = Field(
        description="Additional metadata", 
        default=None
    )


class CustomerInfo(BaseModel):
    name: Optional[str] = Field(description="Tên khách hàng", default=None)
    phone: Optional[str] = Field(description="Số điện thoại", default=None)
    address: Optional[str] = Field(description="Địa chỉ", default=None)
    email: Optional[str] = Field(description="Email", default=None)
    gender: Optional[str] = Field(description="Giới tính", default=None)
    additional_info: Optional[str] = Field(description="Thông tin bổ sung", default=None)


class OrderInfo(BaseModel):
    product_name: str = Field(description="Tên sản phẩm")
    unit_price: float = Field(description="Đơn giá")
    quantity: int = Field(description="Số lượng")
    total_price: float = Field(description="Tổng tiền")
    customer_note: Optional[str] = Field(description="Ghi chú khách hàng", default="")
