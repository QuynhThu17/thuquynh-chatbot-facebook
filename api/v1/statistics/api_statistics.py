from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from api.v1.auth.api_authentication import get_management_factory
from controllers.auth.auth_middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/statistics", tags=["Statistics"])


def _build_extra_filter(
    session_id: Optional[str],
    customer_id: Optional[str],
    bot_id: Optional[str],
    social_id: Optional[str],
    social_page_id: Optional[str],
) -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    if session_id:
        f["session_id"] = session_id
    if customer_id:
        f["customer_id"] = customer_id
    if bot_id:
        f["bot_id"] = bot_id
    if social_id:
        f["social_id"] = social_id
    if social_page_id:
        f["social_page_id"] = social_page_id
    return f


@router.get("/majors/top", response_model=Dict[str, Any])
async def get_top_majors(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    auto_extract: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory),
):
    try:
        user_id = current_user.get("user_id")
        extra = _build_extra_filter(session_id, customer_id, bot_id, social_id, social_page_id)
        if auto_extract:
            await factory.major_statistic_manager.upsert_analysis_for_histories(user_id, extra, max_records=200)
        data = await factory.major_statistic_manager.majors_top(user_id, start_date, end_date, extra, limit)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting top majors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/majors/timeline", response_model=Dict[str, Any])
async def get_majors_timeline(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    auto_extract: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory),
):
    try:
        user_id = current_user.get("user_id")
        extra = _build_extra_filter(session_id, customer_id, bot_id, social_id, social_page_id)
        if auto_extract:
            await factory.major_statistic_manager.upsert_analysis_for_histories(user_id, extra, max_records=200)
        data = await factory.major_statistic_manager.majors_timeline(user_id, start_date, end_date, extra)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting majors timeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/majors/topics", response_model=Dict[str, Any])
async def get_major_topics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    major: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    auto_extract: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory),
):
    try:
        user_id = current_user.get("user_id")
        extra = _build_extra_filter(session_id, customer_id, bot_id, social_id, social_page_id)
        if auto_extract:
            await factory.major_statistic_manager.upsert_analysis_for_histories(user_id, extra, max_records=200)
        data = await factory.major_statistic_manager.topics_distribution(user_id, start_date, end_date, extra, major, limit)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting major topics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/questions/popular", response_model=Dict[str, Any])
async def get_popular_questions(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    auto_extract: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory),
):
    try:
        user_id = current_user.get("user_id")
        extra = _build_extra_filter(session_id, customer_id, bot_id, social_id, social_page_id)
        if auto_extract:
            await factory.major_statistic_manager.upsert_analysis_for_histories(user_id, extra, max_records=200)
        data = await factory.major_statistic_manager.popular_questions(user_id, start_date, end_date, extra, limit)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting popular questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap", response_model=Dict[str, Any])
async def get_heatmap(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    session_id: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    bot_id: Optional[str] = Query(None),
    social_id: Optional[str] = Query(None),
    social_page_id: Optional[str] = Query(None),
    auto_extract: bool = Query(True),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory),
):
    try:
        user_id = current_user.get("user_id")
        extra = _build_extra_filter(session_id, customer_id, bot_id, social_id, social_page_id)
        if auto_extract:
            await factory.major_statistic_manager.upsert_analysis_for_histories(user_id, extra, max_records=200)
        data = await factory.major_statistic_manager.heatmap(user_id, start_date, end_date, extra)
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error getting heatmap: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
