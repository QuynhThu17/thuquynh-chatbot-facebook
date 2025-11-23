"""
Additional Features API Endpoints
Cung cấp API cho usage_tokens, automation, webhooks, templates, analytics
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, HttpUrl
from datetime import datetime
import logging

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.auth.auth_middleware import get_current_user
from configs import environment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/additional", tags=["Additional Features"])

# Pydantic Models
class UsageTokenCreate(BaseModel):
    user_id: str
    service: str  # openai, claude, gemini, etc.
    model: str
    tokens_used: int
    operation_type: str  # chat, completion, embedding, etc.
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = {}


# Dependency to get management factory
def get_management_factory():
    return get_mongodb_factory()

def _normalize_datetime(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(environment.vietnam_tz).replace(tzinfo=None)
    return dt

# Usage Token Endpoints
# @router.post("/usage-tokens", response_model=Dict[str, Any])
# async def create_usage_token(usage_data: UsageTokenCreate, factory = Depends(get_management_factory)):
#     """Ghi nhận usage token"""
#     try:
#         usage_token = await factory.usage_token_manager.create_usage_record(
#             user_id=usage_data.user_id,
#             service=usage_data.service,
#             model=usage_data.model,
#             tokens_used=usage_data.tokens_used,
#             operation_type=usage_data.operation_type,
#             cost=usage_data.cost,
#             metadata=usage_data.metadata
#         )
        
#         return {"success": True, "data": usage_token}
        
#     except Exception as e:
#         logger.error(f"Error creating usage token: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/llm-tokens", response_model=Dict[str, Any])
async def get_llm_token_logs(
    company_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    page_id: Optional[str] = Query(None),
    sender_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy danh sách token logs và cho phép lọc theo các trường cụ thể"""
    try:
        normalized_start = _normalize_datetime(start_time)
        normalized_end = _normalize_datetime(end_time)
        
        user_id = current_user.get("user_id")

        result = await factory.token_log_manager.get_tokens(
            user_id=user_id,
            company_id=company_id,
            bot_id=bot_id,
            page_id=page_id,
            sender_id=sender_id,
            session_id=session_id,
            model=model,
            status=status,
            start_time=normalized_start,
            end_time=normalized_end,
            skip=skip,
            limit=limit,
        )

        error = result.get("error")
        if error:
            raise HTTPException(status_code=500, detail=error)

        return {
            "success": True,
            "data": result.get("items", []),
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": result.get("total", 0)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LLM token logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage-tokens", response_model=Dict[str, Any])
async def get_usage_tokens(
    service: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy usage tokens của user"""
    try:
        user_id = current_user.get("user_id")
        
        usage_tokens = await factory.usage_token_manager.get_user_usage(
            user_id, service, start_date, end_date
        )
        
        # Simple pagination
        total = len(usage_tokens)
        paginated_tokens = usage_tokens[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_tokens,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting usage tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage-tokens/statistics", response_model=Dict[str, Any])
async def get_usage_statistics(
    period: str = Query("month"),  # day, week, month, year
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy thống kê usage tokens"""
    try:
        user_id = current_user.get("user_id")
        
        stats = await factory.usage_token_manager.get_usage_statistics(user_id, period)
        return {"success": True, "data": stats}
        
    except Exception as e:
        logger.error(f"Error getting usage statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/usage-tokens/cost-summary", response_model=Dict[str, Any])
async def get_cost_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """Lấy tổng hợp chi phí"""
    try:
        user_id = current_user.get("user_id")
        
        summary = await factory.usage_token_manager.get_cost_summary(user_id, start_date, end_date)
        return {"success": True, "data": summary}
        
    except Exception as e:
        logger.error(f"Error getting cost summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
