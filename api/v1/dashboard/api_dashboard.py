from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
from bson import ObjectId
import asyncio
from collections import defaultdict
import calendar

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.databases.mongodb.mongodb import MongoDBManager
from controllers.auth.auth_middleware import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Pydantic Models
class DashboardFilters(BaseModel):
    """Filters cho dashboard API"""
    period: Optional[str] = Field("all", description="Thời gian: today, week, month, year, all")
    start_date: Optional[str] = Field(None, description="Ngày bắt đầu (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Ngày kết thúc (YYYY-MM-DD)")
    company_id: Optional[str] = Field(None, description="Lọc theo company_id")

def get_management_factory():
    """Dependency to get management factory"""
    return get_mongodb_factory()

def get_date_range(period: str, start_date: str = None, end_date: str = None) -> tuple:
    """
    Tính toán khoảng thời gian dựa trên period
    Returns: (start_datetime, end_datetime)
    
    Note: Trả về naive datetime (không có timezone) để tương thích với MongoDB
    """
    # Sử dụng datetime.now() không có timezone để tương thích với MongoDB
    now = datetime.now()
    
    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"Custom date range: {start} -> {end}")
        return (start, end)
    
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"Today range: {start} -> {end}")
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=6)
        end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"Week range: {start} -> {end}")
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Tính ngày cuối tháng
        if now.month == 12:
            end = start.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
            end = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"Month range: {start} -> {end}")
    elif period == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"Year range: {start} -> {end}")
    else:  # all
        start = datetime(2020, 1, 1, 0, 0, 0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        logger.debug(f"All time range: {start} -> {end}")
    
    return start, end

def get_previous_date_range(period: str, start_date: datetime, end_date: datetime) -> tuple:
    """
    Tính toán khoảng thời gian trước đó để so sánh
    """
    duration = end_date - start_date
    previous_start = start_date - duration
    previous_end = start_date
    
    return previous_start, previous_end

async def count_documents_in_period(collection, date_field: str, start_date: datetime, 
                                  end_date: datetime, user_filter: dict = None) -> int:
    """
    Đếm documents trong khoảng thời gian
    """
    filter_query = {
        date_field: {
            "$gte": start_date,
            "$lte": end_date  # Đổi từ $lte thành $lte để bao gồm end_date
        }
    }
    
    if user_filter:
        filter_query.update(user_filter)
    
    try:
        count = await collection.count_documents(filter_query)
        logger.debug(f"Count {collection.name} with {date_field} from {start_date} to {end_date}: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting documents in {collection.name}: {str(e)}")
        return 0

async def get_growth_data(collection, date_field: str, start_date: datetime, 
                         end_date: datetime, user_filter: dict = None) -> dict:
    """
    Tính toán dữ liệu tăng trưởng và so sánh với kỳ trước
    """
    # Đếm trong kỳ hiện tại
    current_count = await count_documents_in_period(
        collection, date_field, start_date, end_date, user_filter
    )
    
    # Đếm trong kỳ trước
    prev_start, prev_end = get_previous_date_range("", start_date, end_date)
    previous_count = await count_documents_in_period(
        collection, date_field, prev_start, prev_end, user_filter
    )
    
    # Tính phần trăm tăng trưởng
    growth_rate = 0
    if previous_count > 0:
        growth_rate = ((current_count - previous_count) / previous_count) * 100
    elif current_count > 0:
        growth_rate = 100
    
    logger.debug(f"Growth for {collection.name}: current={current_count}, previous={previous_count}, rate={growth_rate}")
    
    return {
        "current": current_count,
        "previous": previous_count,
        "growth_rate": round(growth_rate, 2),
        "growth_direction": "increase" if growth_rate > 0 else "decrease" if growth_rate < 0 else "stable"
    }

def get_chart_date_range(period: str, start_date: datetime, end_date: datetime) -> tuple:
    """
    Mở rộng date range cho chart để có context so sánh
    
    - today: Lấy thêm 6 ngày trước (tổng 7 ngày)
    - week: Lấy thêm 3 tuần trước (tổng 4 tuần)
    - month: Lấy thêm 2 tháng trước (tổng 3 tháng)
    - year/all: Giữ nguyên
    
    Returns:
        (chart_start_date, chart_end_date, highlight_start): 
        - chart_start_date: Ngày bắt đầu cho chart (có context)
        - chart_end_date: Ngày kết thúc cho chart
        - highlight_start: Ngày bắt đầu của period user chọn (để highlight)
    """
    if period == "today":
        # Lấy thêm 6 ngày trước
        chart_start = start_date - timedelta(days=6)
        return chart_start, end_date, start_date
    elif period == "week":
        # Lấy thêm 3 tuần trước
        chart_start = start_date - timedelta(weeks=3)
        return chart_start, end_date, start_date
    elif period == "month":
        # Lấy thêm 2 tháng trước
        if start_date.month <= 2:
            chart_start = start_date.replace(year=start_date.year - 1, month=start_date.month + 10)
        else:
            chart_start = start_date.replace(month=start_date.month - 2)
        return chart_start, end_date, start_date
    else:
        # year hoặc all - giữ nguyên
        return start_date, end_date, start_date


async def get_chart_data(collection, date_field: str, start_date: datetime, 
                        end_date: datetime, period: str, user_filter: dict = None) -> list:
    """
    Tạo dữ liệu cho biểu đồ theo thời gian (có context cho period ngắn)
    """
    # Mở rộng date range để có context
    chart_start, chart_end, highlight_start = get_chart_date_range(period, start_date, end_date)
    
    pipeline = [
        {
            "$match": {
                date_field: {
                    "$gte": chart_start,  # Dùng chart_start thay vì start_date
                    "$lte": chart_end
                },
                **(user_filter or {})
            }
        }
    ]
    
    # Group theo period
    if period in ["today", "week"]:
        # Group theo giờ
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": f"${date_field}"},
                    "month": {"$month": f"${date_field}"},
                    "day": {"$dayOfMonth": f"${date_field}"},
                    "hour": {"$hour": f"${date_field}"}
                },
                "count": {"$sum": 1}
            }
        })
    elif period == "month":
        # Group theo ngày
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": f"${date_field}"},
                    "month": {"$month": f"${date_field}"},
                    "day": {"$dayOfMonth": f"${date_field}"}
                },
                "count": {"$sum": 1}
            }
        })
    else:
        # Group theo tháng
        pipeline.append({
            "$group": {
                "_id": {
                    "year": {"$year": f"${date_field}"},
                    "month": {"$month": f"${date_field}"}
                },
                "count": {"$sum": 1}
            }
        })
    
    pipeline.append({"$sort": {"_id": 1}})
    
    try:
        result = await collection.aggregate(pipeline).to_list(length=None)
        
        # Tạo dict để lookup count theo date
        count_dict = {}
        for item in result:
            id_data = item["_id"]
            if "hour" in id_data:
                date_str = f"{id_data['year']:04d}-{id_data['month']:02d}-{id_data['day']:02d} {id_data['hour']:02d}:00"
            elif "day" in id_data:
                date_str = f"{id_data['year']:04d}-{id_data['month']:02d}-{id_data['day']:02d}"
            else:
                date_str = f"{id_data['year']:04d}-{id_data['month']:02d}"
            count_dict[date_str] = item["count"]
        
        # Fill missing dates/hours để chart không bị trống
        chart_data = fill_missing_dates(chart_start, chart_end, period, count_dict, highlight_start, end_date)
        
        logger.debug(f"Chart data for {collection.name}: {len(chart_data)} points (filled)")
        return chart_data
    except Exception as e:
        logger.error(f"Error getting chart data from {collection.name}: {str(e)}")
        return []


def fill_missing_dates(start: datetime, end: datetime, period: str, 
                      count_dict: dict, highlight_start: datetime, highlight_end: datetime) -> list:
    """
    Fill các ngày/giờ bị thiếu trong chart data với count = 0
    Đánh dấu period được chọn để FE có thể highlight
    """
    chart_data = []
    current = start
    
    if period in ["today", "week"]:
        # Fill theo giờ (nếu cùng ngày) hoặc theo ngày
        if (end - start).days <= 1:
            # Fill theo giờ
            while current <= end:
                date_str = current.strftime("%Y-%m-%d %H:00")
                is_in_period = highlight_start <= current <= highlight_end
                chart_data.append({
                    "date": date_str,
                    "count": count_dict.get(date_str, 0),
                    "is_current_period": is_in_period  # Đánh dấu period hiện tại
                })
                current += timedelta(hours=1)
        else:
            # Fill theo ngày
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                is_in_period = highlight_start <= current <= highlight_end
                chart_data.append({
                    "date": date_str,
                    "count": count_dict.get(date_str, 0),
                    "is_current_period": is_in_period
                })
                current += timedelta(days=1)
    elif period == "month":
        # Fill theo ngày
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            is_in_period = highlight_start <= current <= highlight_end
            chart_data.append({
                "date": date_str,
                "count": count_dict.get(date_str, 0),
                "is_current_period": is_in_period
            })
            current += timedelta(days=1)
    else:
        # Fill theo tháng (year/all)
        while current <= end:
            date_str = current.strftime("%Y-%m")
            # Check nếu tháng này trong range được chọn
            month_start = current.replace(day=1)
            if current.month == 12:
                month_end = current.replace(month=12, day=31)
            else:
                next_month = current.replace(month=current.month + 1, day=1)
                month_end = next_month - timedelta(days=1)
            
            is_in_period = (month_start >= highlight_start and month_start <= highlight_end) or \
                          (month_end >= highlight_start and month_end <= highlight_end)
            
            chart_data.append({
                "date": date_str,
                "count": count_dict.get(date_str, 0),
                "is_current_period": is_in_period
            })
            # Next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)
    
    return chart_data


@router.get("/overview", response_model=Dict[str, Any])
async def get_dashboard_overview(
    period: str = Query("all", description="Khoảng thời gian: today, week, month, year, all"),
    start_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    company_id: Optional[str] = Query(None, description="Lọc theo company_id"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    🎯 **API Dashboard Tổng Quan Chuyên Nghiệp**
    
    **Tính năng chính:**
    - 📊 Thống kê tổng quan toàn hệ thống theo thời gian thực
    - 📈 So sánh tăng trưởng với kỳ trước  
    - 📉 Dữ liệu biểu đồ chi tiết theo thời gian
    - 🎯 Lọc theo người dùng và công ty
    - 💬 **Tin nhắn mới nhất từ khách hàng (tối đa 7)**
    - 🔔 **Recent Activity - Hoạt động gần đây từ nhiều nguồn**
    - 📋 **Notification Dashboard - Thông báo hệ thống**
    - 📝 **History & Feedback Analytics - Phân tích tương tác**
    
    **Các metrics được theo dõi:**
    - 🤖 Bot System: Số lượng bot, bot active, tin nhắn, tỷ lệ phản hồi
    - 📱 Social Media: Tài khoản kết nối, Facebook pages active
    - 👥 Khách hàng: Khách hàng mới, tăng trưởng khách hàng
    - 🛒 Đơn hàng: Đơn hàng mới, doanh thu, tỷ lệ chuyển đổi
    - 📚 Kiến thức: Documents, knowledge chunks
    - 💬 Hoạt động: Chat histories, feedback
    
    **Parameters:**
    - `period`: Khoảng thời gian (today/week/month/year/all)
    - `start_date`, `end_date`: Custom date range (YYYY-MM-DD)
    - `company_id`: Lọc theo công ty cụ thể
    
    **Response Format:**
    ```json
    {
        "success": true,
        "data": {
            "summary": {
                "bots": {...},
                "social": {...}, 
                "customers": {...},
                "orders": {...},
                "knowledge": {...},
                "activities": {...}
            },
            "charts": {...},
            "recent_customer_messages": {
                "title": "Tin nhắn mới nhất từ khách hàng",
                "data": [...],
                "total_customers": 7
            },
            "recent_activity": {
                "title": "Hoạt động gần đây",
                "data": [
                    {
                        "type": "message|notification|feedback|login|order",
                        "title": "...",
                        "content": "...",
                        "timestamp": "...",
                        "source": "Facebook|Website|System",
                        "priority": "high|medium|low",
                        "status": "...",
                        "metadata": {...}
                    }
                ],
                "total_activities": 15
            },
            "notifications_summary": {
                "unread_count": 5,
                "by_type": {...},
                "recent": [...]
            },
            "metadata": {...}
        }
    }
    ```
    """
    try:
        user_id = current_user.get("user_id")
        start_datetime, end_datetime = get_date_range(period, start_date, end_date)
        
        logger.info(f"🎯 Dashboard overview request - user_id: {user_id}, period: {period}")
        logger.info(f"📅 Date range: {start_datetime} -> {end_datetime}")
        
        # Base filter cho user
        user_filter = {"user_id": user_id}
        if company_id:
            user_filter["company_id"] = company_id
        
                # Parallel queries để tối ưu performance
        tasks = [
            get_bot_metrics(factory, start_datetime, end_datetime, user_filter),
            get_social_metrics(factory, start_datetime, end_datetime, user_filter),
            get_customer_metrics(factory, start_datetime, end_datetime, user_filter),
            get_order_metrics(factory, start_datetime, end_datetime, user_filter),
            get_knowledge_metrics(factory, start_datetime, end_datetime, user_filter),
            get_activity_metrics(factory, start_datetime, end_datetime, user_filter),
            get_recent_customer_messages(factory, user_filter, 7),
            get_recent_activity(factory, user_filter, 15),  # Thêm recent activity
            get_notifications_summary(factory, user_filter),  # Thêm notifications summary
            get_dashboard_charts(factory, start_datetime, end_datetime, period, user_filter)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Xử lý kết quả
        bot_metrics = results[0] if not isinstance(results[0], Exception) else {"error": str(results[0])}
        social_metrics = results[1] if not isinstance(results[1], Exception) else {"error": str(results[1])}
        customer_metrics = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}
        order_metrics = results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])}
        knowledge_metrics = results[4] if not isinstance(results[4], Exception) else {"error": str(results[4])}
        activity_metrics = results[5] if not isinstance(results[5], Exception) else {"error": str(results[5])}
        recent_messages = results[6] if not isinstance(results[6], Exception) else []
        recent_activity = results[7] if not isinstance(results[7], Exception) else []
        notifications_summary = results[8] if not isinstance(results[8], Exception) else {}
        charts_data = results[9] if not isinstance(results[9], Exception) else {"error": str(results[9])}
        
        return {
            "success": True,
            "data": {
                "summary": {
                    "bots": bot_metrics,
                    "social": social_metrics, 
                    "customers": customer_metrics,
                    "orders": order_metrics,
                    "knowledge": knowledge_metrics,
                    "activities": activity_metrics
                },
                "charts": charts_data,
                "recent_customer_messages": {
                    "title": "Tin nhắn mới nhất từ khách hàng",
                    "data": recent_messages,
                    "total_customers": len(recent_messages)
                },
                "recent_activity": {
                    "title": "Hoạt động gần đây",
                    "data": recent_activity,
                    "total_activities": len(recent_activity)
                },
                "notifications_summary": notifications_summary,
                "metadata": {
                    "period": period,
                    "start_date": start_datetime.isoformat(),
                    "end_date": end_datetime.isoformat(),
                    "user_id": user_id,
                    "company_id": company_id,
                    "generated_at": datetime.now().isoformat()
                }
            }
        }
        results = await asyncio.gather(
            # Bot metrics
            get_bot_metrics(factory, start_datetime, end_datetime, user_filter),
            # Social metrics  
            get_social_metrics(factory, start_datetime, end_datetime, user_filter),
            # Customer metrics
            get_customer_metrics(factory, start_datetime, end_datetime, user_filter),
            # Order metrics
            get_order_metrics(factory, start_datetime, end_datetime, user_filter),
            # Knowledge metrics
            get_knowledge_metrics(factory, start_datetime, end_datetime, user_filter),
            # Activity metrics
            get_activity_metrics(factory, start_datetime, end_datetime, user_filter),
            # Chart data
            get_dashboard_charts(factory, start_datetime, end_datetime, period, user_filter),
            # Recent customer messages
            get_recent_customer_messages(factory, user_filter, 7)
        )
        
        bot_metrics, social_metrics, customer_metrics, order_metrics, knowledge_metrics, activity_metrics, chart_data, recent_messages = results
        
        return {
            "success": True,
            "data": {
                "summary": {
                    "bots": bot_metrics,
                    "social": social_metrics,
                    "customers": customer_metrics, 
                    "orders": order_metrics,
                    "knowledge": knowledge_metrics,
                    "activities": activity_metrics
                },
                "charts": chart_data,
                "recent_customer_messages": {
                    "title": "Tin nhắn mới nhất từ khách hàng",
                    "description": "7 tin nhắn mới nhất từ các khách hàng khác nhau",
                    "data": recent_messages,
                    "total_customers": len(recent_messages)
                },
                "metadata": {
                    "period": period,
                    "start_date": start_datetime.strftime("%Y-%m-%d"),
                    "end_date": end_datetime.strftime("%Y-%m-%d"),
                    "user_id": user_id,
                    "company_id": company_id,
                    "generated_at": datetime.now().isoformat(),
                    "timezone": "Asia/Ho_Chi_Minh"
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting dashboard overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")


async def get_bot_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """🤖 Thống kê Bot System"""
    try:
        bot_collection = factory._db_manager.database["bots"]
        history_collection = factory._db_manager.database["histories"]
        
        # Total bots
        total_bots = await bot_collection.count_documents(user_filter)
        
        # Active bots (status = "on")
        active_filter = {**user_filter, "status": "on"}
        active_bots = await bot_collection.count_documents(active_filter)
        
        # New bots in period
        new_bots_data = await get_growth_data(
            bot_collection, "create_at", start_date, end_date, user_filter
        )
        
        # Messages in period
        message_filter = {**user_filter}
        messages_data = await get_growth_data(
            history_collection, "created_at", start_date, end_date, message_filter
        )
        
        # Response rate calculation
        total_messages = await history_collection.count_documents({
            **message_filter,
            "created_at": {"$gte": start_date, "$lte": end_date}
        })
        
        responded_messages = await history_collection.count_documents({
            **message_filter,
            "created_at": {"$gte": start_date, "$lte": end_date},
            "answer": {"$exists": True, "$ne": ""}
        })
        
        response_rate = (responded_messages / total_messages * 100) if total_messages > 0 else 0
        
        return {
            "total_bots": {
                "count": total_bots,
                "active": active_bots,
                "inactive": total_bots - active_bots,
                "active_rate": (active_bots / total_bots * 100) if total_bots > 0 else 0
            },
            "new_bots": new_bots_data,
            "messages": messages_data,
            "performance": {
                "response_rate": round(response_rate, 2),
                "total_conversations": total_messages,
                "successful_responses": responded_messages
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting bot metrics: {str(e)}")
        return {"error": str(e)}


async def get_social_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """📱 Thống kê Social Media"""
    try:
        social_accounts_collection = factory._db_manager.database["social_accounts"]
        facebook_pages_collection = factory._db_manager.database["social_facebook_pages"]
        
        # Total social accounts
        total_accounts = await social_accounts_collection.count_documents(user_filter)
        
        # Facebook accounts
        facebook_filter = {**user_filter, "social_id": "s_facebook"}
        facebook_accounts = await social_accounts_collection.count_documents(facebook_filter)
        
        # Facebook pages
        facebook_pages_filter = {"social_account_id": {"$exists": True}}
        if user_filter.get("user_id"):
            # Cần join với social_accounts để lấy user_id
            pipeline = [
                {"$lookup": {
                    "from": "social_accounts",
                    "localField": "social_account_id", 
                    "foreignField": "_id",
                    "as": "account"
                }},
                {"$match": {"account.user_id": user_filter["user_id"]}}
            ]
            facebook_pages_docs = await facebook_pages_collection.aggregate(pipeline).to_list(length=None)
            total_facebook_pages = len(facebook_pages_docs)
            active_facebook_pages = len([doc for doc in facebook_pages_docs if doc.get("is_connected")])
        else:
            total_facebook_pages = await facebook_pages_collection.count_documents({})
            active_facebook_pages = await facebook_pages_collection.count_documents({"is_connected": True})
        
        # New social accounts in period
        new_accounts_data = await get_growth_data(
            social_accounts_collection, "create_at", start_date, end_date, user_filter
        )
        
        return {
            "total_accounts": {
                "count": total_accounts,
                "facebook": facebook_accounts,
                "other_platforms": total_accounts - facebook_accounts
            },
            "facebook_pages": {
                "total": total_facebook_pages,
                "active": active_facebook_pages,
                "inactive": total_facebook_pages - active_facebook_pages,
                "connection_rate": (active_facebook_pages / total_facebook_pages * 100) if total_facebook_pages > 0 else 0
            },
            "new_accounts": new_accounts_data
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting social metrics: {str(e)}")
        return {"error": str(e)}


async def get_customer_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """👥 Thống kê Khách hàng"""
    try:
        contacts_collection = factory._db_manager.database["contacts"]
        
        # Total customers
        total_customers = await contacts_collection.count_documents(user_filter)
        
        # New customers in period
        new_customers_data = await get_growth_data(
            contacts_collection, "create_at", start_date, end_date, user_filter
        )
        
        # Customer types analysis
        customer_pipeline = [
            {"$match": user_filter},
            {"$group": {
                "_id": "$type",
                "count": {"$sum": 1}
            }}
        ]
        customer_types = await contacts_collection.aggregate(customer_pipeline).to_list(length=None)
        
        types_summary = {}
        for item in customer_types:
            types_summary[item["_id"] or "unknown"] = item["count"]
        
        return {
            "total_customers": total_customers,
            "new_customers": new_customers_data,
            "customer_types": types_summary,
            "growth_trend": {
                "direction": new_customers_data.get("growth_direction", "stable"),
                "rate": new_customers_data.get("growth_rate", 0)
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting customer metrics: {str(e)}")
        return {"error": str(e)}


async def get_order_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """🛒 Thống kê Đơn hàng"""
    try:
        orders_collection = factory._db_manager.database["orders"]
        
        # Total orders
        total_orders = await orders_collection.count_documents(user_filter)
        
        # New orders in period
        new_orders_data = await get_growth_data(
            orders_collection, "create_at", start_date, end_date, user_filter
        )
        
        # Order status analysis
        status_pipeline = [
            {"$match": {
                **user_filter,
                "create_at": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$total_amount"}
            }}
        ]
        status_analysis = await orders_collection.aggregate(status_pipeline).to_list(length=None)
        
        status_summary = {}
        total_revenue = 0
        for item in status_analysis:
            status_summary[item["_id"] or "unknown"] = {
                "count": item["count"],
                "revenue": item.get("total_value", 0)
            }
            total_revenue += item.get("total_value", 0)
        
        # Average order value
        avg_order_value = total_revenue / new_orders_data["current"] if new_orders_data["current"] > 0 else 0
        
        return {
            "total_orders": total_orders,
            "new_orders": new_orders_data,
            "revenue": {
                "total": total_revenue,
                "average_order_value": round(avg_order_value, 2),
                "currency": "VND"
            },
            "order_status": status_summary
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting order metrics: {str(e)}")
        return {"error": str(e)}


async def get_knowledge_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """📚 Thống kê Kiến thức"""
    try:
        documents_collection = factory._db_manager.database["documents"]
        chunks_collection = factory._db_manager.database["knowledge_chunks"]
        
        # Total documents
        total_documents = await documents_collection.count_documents(user_filter)
        
        # New documents in period
        new_documents_data = await get_growth_data(
            documents_collection, "create_at", start_date, end_date, user_filter
        )
        
        # Document status analysis
        status_pipeline = [
            {"$match": user_filter},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        document_status = await documents_collection.aggregate(status_pipeline).to_list(length=None)
        
        status_summary = {}
        for item in document_status:
            status_summary[item["_id"] or "unknown"] = item["count"]
        
        # Knowledge chunks total
        total_chunks = await chunks_collection.count_documents(user_filter)
        
        # File type analysis
        file_type_pipeline = [
            {"$match": user_filter},
            {"$group": {
                "_id": "$file_type",
                "count": {"$sum": 1}
            }}
        ]
        file_types = await documents_collection.aggregate(file_type_pipeline).to_list(length=None)
        
        file_types_summary = {}
        for item in file_types:
            file_types_summary[item["_id"] or "unknown"] = item["count"]
        
        return {
            "total_documents": total_documents,
            "new_documents": new_documents_data,
            "document_status": status_summary,
            "knowledge_chunks": total_chunks,
            "file_types": file_types_summary,
            "processing_rate": (status_summary.get("processed", 0) / total_documents * 100) if total_documents > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting knowledge metrics: {str(e)}")
        return {"error": str(e)}


async def get_activity_metrics(factory, start_date: datetime, end_date: datetime, user_filter: dict) -> dict:
    """💬 Thống kê Hoạt động"""
    try:
        histories_collection = factory._db_manager.database["histories"]
        feedback_collection = factory._db_manager.database["feedback"]
        
        # Chat activities
        chat_activities_data = await get_growth_data(
            histories_collection, "created_at", start_date, end_date, user_filter
        )
        
        # Feedback activities
        feedback_activities_data = await get_growth_data(
            feedback_collection, "create_at", start_date, end_date, user_filter
        )
        
        # Unique sessions in period
        session_pipeline = [
            {"$match": {
                **user_filter,
                "created_at": {"$gte": start_date, "$lte": end_date}
            }},
            {"$group": {
                "_id": "$session_id"
            }},
            {"$count": "unique_sessions"}
        ]
        session_result = await histories_collection.aggregate(session_pipeline).to_list(length=None)
        unique_sessions = session_result[0]["unique_sessions"] if session_result else 0
        
        # Average messages per session
        avg_messages_per_session = chat_activities_data["current"] / unique_sessions if unique_sessions > 0 else 0
        
        return {
            "chat_activities": chat_activities_data,
            "feedback_activities": feedback_activities_data,
            "engagement": {
                "unique_sessions": unique_sessions,
                "avg_messages_per_session": round(avg_messages_per_session, 2),
                "total_interactions": chat_activities_data["current"] + feedback_activities_data["current"]
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting activity metrics: {str(e)}")
        return {"error": str(e)}


async def get_recent_activity(factory, user_filter: dict, limit: int = 15) -> list:
    """
    🔔 Lấy hoạt động gần đây từ nhiều nguồn: notifications, histories, feedback, orders, etc.
    
    Args:
        factory: Database factory
        user_filter: Filter theo user_id
        limit: Số lượng tối đa (default: 15)
        
    Returns:
        List[Dict]: Danh sách hoạt động gần đây được sắp xếp theo thời gian
    """
    try:
        # Collections
        notifications_collection = factory._db_manager.database["notifications"]
        histories_collection = factory._db_manager.database["histories"]
        feedback_collection = factory._db_manager.database["feedback"]
        orders_collection = factory._db_manager.database["orders"]
        social_accounts_collection = factory._db_manager.database["social_accounts"]
        bots_collection = factory._db_manager.database["bots"]
        
        # Recent activities from different sources
        activities = []
        
        # 1. Recent Notifications (5 items)
        notifications = await notifications_collection.find(
            user_filter,
            {"title": 1, "content": 1, "notification_type": 1, "category": 1, 
             "priority": 1, "is_read": 1, "created_at": 1, "action": 1, "metadata": 1}
        ).sort("created_at", -1).limit(5).to_list(length=None)
        
        for notif in notifications:
            activities.append({
                "type": "notification",
                "title": notif.get("title", "Thông báo"),
                "content": notif.get("content", ""),
                "timestamp": notif.get("created_at"),
                "source": "System",
                "priority": "high" if notif.get("priority", 1) >= 4 else "medium" if notif.get("priority", 1) >= 2 else "low",
                "status": "unread" if not notif.get("is_read", False) else "read",
                "icon": get_notification_icon(notif.get("category", "system")),
                "color": get_notification_color(notif.get("notification_type", "info")),
                "metadata": {
                    "category": notif.get("category"),
                    "action": notif.get("action"),
                    "notification_type": notif.get("notification_type")
                }
            })
        
        # 2. Recent Messages/Conversations (4 items)
        recent_messages = await histories_collection.find(
            {**user_filter, "query": {"$exists": True, "$ne": ""}},
            {"query": 1, "answer": 1, "session_id": 1, "created_at": 1, 
             "bot_id": 1, "social_id": 1, "customer_id": 1}
        ).sort("created_at", -1).limit(4).to_list(length=None)
        
        for msg in recent_messages:
            customer_name = await get_customer_name(factory, msg.get("customer_id")) or "Khách hàng"
            social_name = await get_social_name(factory, msg.get("social_id")) or "Website"
            
            activities.append({
                "type": "message",
                "title": f"{customer_name} đã gửi tin nhắn",
                "content": truncate_text(msg.get("query", ""), 100),
                "timestamp": msg.get("created_at"),
                "source": social_name,
                "priority": "medium",
                "status": "new",
                "icon": "💬",
                "color": "blue",
                "metadata": {
                    "session_id": msg.get("session_id"),
                    "bot_id": msg.get("bot_id"),
                    "has_answer": bool(msg.get("answer"))
                }
            })
        
        # 3. Recent Feedback (3 items)
        recent_feedback = await feedback_collection.find(
            user_filter,
            {"content": 1, "status": 1, "social_id": 1, "social_identification": 1, "create_at": 1}
        ).sort("create_at", -1).limit(3).to_list(length=None)
        
        for feedback in recent_feedback:
            rating_stars = get_feedback_rating(feedback.get("content", ""))
            social_name = await get_social_name(factory, feedback.get("social_id")) or "Website"
            
            activities.append({
                "type": "feedback",
                "title": f"Phản hồi mới từ khách hàng",
                "content": truncate_text(feedback.get("content", ""), 100),
                "timestamp": feedback.get("create_at"),
                "source": social_name,
                "priority": "medium",
                "status": feedback.get("status", "new"),
                "icon": rating_stars or "⭐",
                "color": "yellow",
                "metadata": {
                    "social_identification": feedback.get("social_identification"),
                    "rating": rating_stars
                }
            })
        
        # 4. Recent Orders (3 items)
        if await orders_collection.count_documents(user_filter) > 0:
            recent_orders = await orders_collection.find(
                user_filter,
                {"order_id": 1, "total_amount": 1, "status": 1, "customer_id": 1, "create_at": 1}
            ).sort("create_at", -1).limit(3).to_list(length=None)
            
            for order in recent_orders:
                customer_name = await get_customer_name(factory, order.get("customer_id")) or "Khách hàng"
                
                activities.append({
                    "type": "order",
                    "title": f"Đơn hàng mới từ {customer_name}",
                    "content": f"Giá trị: {format_currency(order.get('total_amount', 0))}",
                    "timestamp": order.get("create_at"),
                    "source": "Website",
                    "priority": "high",
                    "status": order.get("status", "pending"),
                    "icon": "🛒",
                    "color": "green",
                    "metadata": {
                        "order_id": order.get("order_id"),
                        "amount": order.get("total_amount")
                    }
                })
        
        # Sort by timestamp descending và limit
        activities.sort(key=lambda x: x.get("timestamp") or datetime.min, reverse=True)
        activities = activities[:limit]
        
        # Format timestamp for display và serialize
        for activity in activities:
            if activity.get("timestamp"):
                activity["timestamp_display"] = format_relative_time(activity["timestamp"])
                # Convert datetime to ISO string if needed
                if isinstance(activity["timestamp"], datetime):
                    activity["timestamp"] = activity["timestamp"].isoformat()
        
        logger.info(f"✅ Lấy {len(activities)} hoạt động gần đây")
        return activities
        
    except Exception as e:
        logger.error(f"❌ Error getting recent activity: {str(e)}")
        return []


async def get_notifications_summary(factory, user_filter: dict) -> dict:
    """
    🔔 Lấy tóm tắt notifications
    """
    try:
        notifications_collection = factory._db_manager.database["notifications"]
        
        # Unread notifications count
        unread_count = await notifications_collection.count_documents({
            **user_filter,
            "is_read": False
        })
        
        # By type breakdown
        type_pipeline = [
            {"$match": user_filter},
            {"$group": {
                "_id": "$notification_type",
                "count": {"$sum": 1},
                "unread": {"$sum": {"$cond": [{"$eq": ["$is_read", False]}, 1, 0]}}
            }}
        ]
        
        type_stats = await notifications_collection.aggregate(type_pipeline).to_list(length=None)
        by_type = {}
        for stat in type_stats:
            by_type[stat["_id"]] = {
                "total": stat["count"],
                "unread": stat["unread"]
            }
        
        # Recent notifications (3 most recent)
        recent = await notifications_collection.find(
            user_filter,
            {"title": 1, "notification_type": 1, "created_at": 1, "is_read": 1}
        ).sort("created_at", -1).limit(3).to_list(length=None)
        
        return {
            "unread_count": unread_count,
            "by_type": by_type,
            "recent": serialize_documents(recent)
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting notifications summary: {str(e)}")
        return {"unread_count": 0, "by_type": {}, "recent": []}


# Helper functions
def get_notification_icon(category: str) -> str:
    """Lấy icon cho notification category"""
    icons = {
        "system": "⚙️", "auth": "🔐", "bot": "🤖", "social": "📱",
        "conversation": "💬", "business": "🏢", "user": "👤", "crm": "📊",
        "knowledge": "📚", "payment": "💳", "subscription": "📋",
        "integration": "🔗", "analytics": "📈", "security": "🛡️", "error": "❌"
    }
    return icons.get(category, "🔔")


def get_notification_color(notification_type: str) -> str:
    """Lấy màu cho notification type"""
    colors = {
        "info": "blue", "success": "green", "warning": "yellow",
        "error": "red", "alert": "orange"
    }
    return colors.get(notification_type, "gray")


def get_feedback_rating(content: str) -> str:
    """Phân tích rating từ feedback content"""
    content_lower = content.lower()
    if any(word in content_lower for word in ["tốt", "tuyệt", "hài lòng", "xuất sắc", "good", "excellent"]):
        return "⭐⭐⭐⭐⭐"
    elif any(word in content_lower for word in ["ổn", "ok", "không tệ", "average"]):
        return "⭐⭐⭐"
    elif any(word in content_lower for word in ["tệ", "kém", "không hài lòng", "bad", "poor"]):
        return "⭐⭐"
    return "⭐⭐⭐⭐"  # Default 4 stars


def truncate_text(text: str, max_length: int = 100) -> str:
    """Cắt ngắn text"""
    if not text:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text


def format_currency(amount: float) -> str:
    """Format currency VND"""
    return f"{int(amount):,} VND" if amount else "0 VND"


def format_relative_time(timestamp) -> str:
    """Format thời gian tương đối"""
    if not timestamp:
        return "Không xác định"
    
    now = datetime.now()
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} ngày trước"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} giờ trước"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} phút trước"
    else:
        return "Vừa xong"


async def get_customer_name(factory, customer_id: str) -> Optional[str]:
    """Lấy tên khách hàng"""
    if not customer_id:
        return None
    try:
        contacts_collection = factory._db_manager.database["contacts"]
        # Handle both ObjectId and string format
        if isinstance(customer_id, str) and len(customer_id) == 24:
            try:
                query = {"_id": ObjectId(customer_id)}
            except:
                query = {"_id": customer_id}
        else:
            query = {"_id": customer_id}
            
        customer = await contacts_collection.find_one(query, {"name": 1, "full_name": 1})
        if customer:
            return customer.get("full_name") or customer.get("name")
    except Exception as e:
        logger.debug(f"Error getting customer name: {e}")
        pass
    return None


async def get_social_name(factory, social_id: str) -> Optional[str]:
    """Lấy tên social platform"""
    if not social_id:
        return None
    try:
        socials_collection = factory._db_manager.database["socials"]
        social = await socials_collection.find_one(
            {"_id": social_id},
            {"name": 1}
        )
        if social:
            return social.get("name")
    except:
        pass
    return None


async def get_recent_customer_messages(factory, user_filter: dict, limit: int = 7) -> list:
    """
    💬 Lấy tin nhắn mới nhất từ khách hàng
    
    Args:
        factory: Database factory
        user_filter: Filter theo user_id
        limit: Số lượng tối đa (default: 7)
        
    Returns:
        List[Dict]: Danh sách tin nhắn mới nhất từ khách hàng
    """
    try:
        histories_collection = factory._db_manager.database["histories"]
        
        # Pipeline để lấy tin nhắn mới nhất từ mỗi session_id (khách hàng)
        pipeline = [
            # Match theo user_id và chỉ lấy tin nhắn từ khách hàng (query không rỗng)
            {
                "$match": {
                    **user_filter,
                    "query": {"$exists": True, "$ne": ""},  # Tin nhắn từ khách hàng
                    "session_id": {"$exists": True, "$ne": ""}  # Phải có session_id
                }
            },
            # Sort theo thời gian tạo (mới nhất trước)
            {
                "$sort": {"created_at": -1}
            },
            # Group theo session_id và lấy tin nhắn mới nhất
            {
                "$group": {
                    "_id": "$session_id",
                    "latest_message": {"$first": "$$ROOT"},  # Lấy document đầu tiên (mới nhất)
                    "customer_id": {"$first": "$customer_id"},
                    "last_message_time": {"$first": "$created_at"}
                }
            },
            # Sort lại theo thời gian tin nhắn mới nhất
            {
                "$sort": {"last_message_time": -1}
            },
            # Limit số lượng khách hàng
            {
                "$limit": limit
            },
            # Project để format output
            {
                "$project": {
                    "_id": 0,
                    "session_id": "$_id",
                    "customer_id": "$customer_id",
                    "history_id": "$latest_message.history_id",
                    "query": "$latest_message.query",
                    "answer": "$latest_message.answer",
                    "media": "$latest_message.media",
                    "status": "$latest_message.status",
                    "bot_id": "$latest_message.bot_id",
                    "social_id": "$latest_message.social_id",
                    "social_page_id": "$latest_message.social_page_id",
                    "created_at": "$latest_message.created_at",
                    "updated_at": "$latest_message.updated_at",
                    "last_message_time": 1
                }
            }
        ]
        
        cursor = histories_collection.aggregate(pipeline)
        recent_messages = await cursor.to_list(length=None)
        
        # Serialize ObjectIds to strings
        serialized_messages = serialize_documents(recent_messages)
        
        logger.info(f"✅ Lấy {len(serialized_messages)} tin nhắn mới nhất từ khách hàng")
        return serialized_messages
        
    except Exception as e:
        logger.error(f"❌ Error getting recent customer messages: {str(e)}")
        return []


async def get_dashboard_charts(factory, start_date: datetime, end_date: datetime, period: str, user_filter: dict) -> dict:
    """📈 Dữ liệu biểu đồ đầy đủ cho dashboard"""
    try:
        # Collections
        histories_collection = factory._db_manager.database["histories"]
        orders_collection = factory._db_manager.database["orders"]
        contacts_collection = factory._db_manager.database["contacts"]
        documents_collection = factory._db_manager.database["documents"]
        feedback_collection = factory._db_manager.database["feedback"]
        notifications_collection = factory._db_manager.database["notifications"]
        bots_collection = factory._db_manager.database["bots"]
        social_accounts_collection = factory._db_manager.database["social_accounts"]
        
        # Parallel chart data queries
        charts_data = await asyncio.gather(
            get_chart_data(histories_collection, "created_at", start_date, end_date, period, user_filter),
            get_chart_data(orders_collection, "create_at", start_date, end_date, period, user_filter),
            get_chart_data(contacts_collection, "create_at", start_date, end_date, period, user_filter),
            get_chart_data(documents_collection, "create_at", start_date, end_date, period, user_filter),
            get_chart_data(feedback_collection, "create_at", start_date, end_date, period, user_filter),
            get_chart_data(notifications_collection, "created_at", start_date, end_date, period, user_filter),
            get_chart_data(bots_collection, "create_at", start_date, end_date, period, user_filter),
            get_chart_data(social_accounts_collection, "create_at", start_date, end_date, period, user_filter),
            get_performance_metrics_chart(factory, start_date, end_date, period, user_filter),
            get_user_engagement_chart(factory, start_date, end_date, period, user_filter),
            get_revenue_chart(factory, start_date, end_date, period, user_filter)
        )
        
        return {
            "timeline_charts": {
                "messages_timeline": {
                    "title": "Tin nhắn theo thời gian",
                    "data": charts_data[0],
                    "type": "line",
                    "color": "#3B82F6",
                    "icon": "💬"
                },
                "orders_timeline": {
                    "title": "Đơn hàng theo thời gian", 
                    "data": charts_data[1],
                    "type": "bar",
                    "color": "#10B981",
                    "icon": "🛒"
                },
                "customers_timeline": {
                    "title": "Khách hàng mới theo thời gian",
                    "data": charts_data[2], 
                    "type": "area",
                    "color": "#8B5CF6",
                    "icon": "👥"
                },
                "documents_timeline": {
                    "title": "Tài liệu theo thời gian",
                    "data": charts_data[3],
                    "type": "line",
                    "color": "#F59E0B",
                    "icon": "📚"
                },
                "feedback_timeline": {
                    "title": "Phản hồi theo thời gian",
                    "data": charts_data[4],
                    "type": "bar",
                    "color": "#EF4444",
                    "icon": "⭐"
                },
                "notifications_timeline": {
                    "title": "Thông báo theo thời gian",
                    "data": charts_data[5],
                    "type": "line",
                    "color": "#6366F1",
                    "icon": "🔔"
                },
                "bots_timeline": {
                    "title": "Bot tạo mới theo thời gian",
                    "data": charts_data[6],
                    "type": "step",
                    "color": "#14B8A6",
                    "icon": "🤖"
                },
                "social_accounts_timeline": {
                    "title": "Tài khoản social theo thời gian",
                    "data": charts_data[7],
                    "type": "area",
                    "color": "#F97316",
                    "icon": "📱"
                }
            },
            "analytics_charts": {
                "performance_metrics": charts_data[8],
                "user_engagement": charts_data[9],
                "revenue_analysis": charts_data[10]
            },
            "summary": {
                "total_charts": 11,
                "period": period,
                "date_range": f"{start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}"
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting chart data: {str(e)}")
        return {"error": str(e)}


async def get_performance_metrics_chart(factory, start_date: datetime, end_date: datetime, period: str, user_filter: dict) -> dict:
    """📊 Biểu đồ performance metrics (có context cho period ngắn)"""
    try:
        histories_collection = factory._db_manager.database["histories"]
        
        # Mở rộng date range để có context
        chart_start, chart_end, highlight_start = get_chart_date_range(period, start_date, end_date)
        
        # Response rate over time
        pipeline = [
            {
                "$match": {
                    **user_filter,
                    "created_at": {"$gte": chart_start, "$lte": chart_end}  # Dùng chart range
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"},
                        "day": {"$dayOfMonth": "$created_at"}
                    },
                    "total_messages": {"$sum": 1},
                    "answered_messages": {
                        "$sum": {
                            "$cond": [
                                {"$and": [
                                    {"$ne": ["$answer", None]},
                                    {"$ne": ["$answer", ""]}
                                ]}, 1, 0
                            ]
                        }
                    }
                }
            },
            {
                "$addFields": {
                    "response_rate": {
                        "$multiply": [
                            {"$divide": ["$answered_messages", "$total_messages"]},
                            100
                        ]
                    }
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        result = await histories_collection.aggregate(pipeline).to_list(length=None)
        
        # Tạo dict để lookup
        metrics_dict = {}
        for item in result:
            id_data = item["_id"]
            date_str = f"{id_data['year']:04d}-{id_data['month']:02d}-{id_data['day']:02d}"
            metrics_dict[date_str] = {
                "response_rate": round(item["response_rate"], 2),
                "total_messages": item["total_messages"],
                "answered_messages": item["answered_messages"]
            }
        
        # Fill missing dates
        chart_data = []
        current = chart_start.replace(hour=0, minute=0, second=0, microsecond=0)
        while current <= chart_end:
            date_str = current.strftime("%Y-%m-%d")
            is_in_period = highlight_start <= current <= end_date
            
            if date_str in metrics_dict:
                data_point = metrics_dict[date_str].copy()
            else:
                data_point = {
                    "response_rate": 0,
                    "total_messages": 0,
                    "answered_messages": 0
                }
            
            data_point["date"] = date_str
            data_point["is_current_period"] = is_in_period
            chart_data.append(data_point)
            current += timedelta(days=1)
        
        return {
            "title": "Tỷ lệ phản hồi theo thời gian",
            "type": "line",
            "color": "#059669",
            "data": chart_data,
            "metrics": ["response_rate", "total_messages"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting performance metrics chart: {str(e)}")
        return {"title": "Performance Metrics", "data": [], "error": str(e)}


async def get_user_engagement_chart(factory, start_date: datetime, end_date: datetime, period: str, user_filter: dict) -> dict:
    """👥 Biểu đồ user engagement (có context cho period ngắn)"""
    try:
        histories_collection = factory._db_manager.database["histories"]
        
        # Mở rộng date range để có context
        chart_start, chart_end, highlight_start = get_chart_date_range(period, start_date, end_date)
        
        # User engagement metrics
        pipeline = [
            {
                "$match": {
                    **user_filter,
                    "created_at": {"$gte": chart_start, "$lte": chart_end}  # Dùng chart range
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "session_id": "$session_id"
                    },
                    "messages_count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": "$_id.date",
                    "unique_sessions": {"$sum": 1},
                    "total_messages": {"$sum": "$messages_count"},
                    "avg_messages_per_session": {"$avg": "$messages_count"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        result = await histories_collection.aggregate(pipeline).to_list(length=None)
        
        # Tạo dict để lookup
        engagement_dict = {}
        for item in result:
            engagement_dict[item["_id"]] = {
                "unique_sessions": item["unique_sessions"],
                "total_messages": item["total_messages"],
                "avg_messages_per_session": round(item["avg_messages_per_session"], 2)
            }
        
        # Fill missing dates
        chart_data = []
        current = chart_start.replace(hour=0, minute=0, second=0, microsecond=0)
        while current <= chart_end:
            date_str = current.strftime("%Y-%m-%d")
            is_in_period = highlight_start <= current <= end_date
            
            if date_str in engagement_dict:
                data_point = engagement_dict[date_str].copy()
            else:
                data_point = {
                    "unique_sessions": 0,
                    "total_messages": 0,
                    "avg_messages_per_session": 0
                }
            
            data_point["date"] = date_str
            data_point["is_current_period"] = is_in_period
            chart_data.append(data_point)
            current += timedelta(days=1)
        
        return {
            "title": "Mức độ tương tác người dùng",
            "type": "combo",
            "color": "#7C3AED",
            "data": chart_data,
            "metrics": ["unique_sessions", "avg_messages_per_session"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting user engagement chart: {str(e)}")
        return {"title": "User Engagement", "data": [], "error": str(e)}


async def get_revenue_chart(factory, start_date: datetime, end_date: datetime, period: str, user_filter: dict) -> dict:
    """💰 Biểu đồ doanh thu (có context cho period ngắn)"""
    try:
        orders_collection = factory._db_manager.database["orders"]
        
        # Mở rộng date range để có context
        chart_start, chart_end, highlight_start = get_chart_date_range(period, start_date, end_date)
        
        # Revenue analysis
        pipeline = [
            {
                "$match": {
                    **user_filter,
                    "create_at": {"$gte": chart_start, "$lte": chart_end}  # Dùng chart range
                }
            },
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$create_at"}},
                        "status": "$status"
                    },
                    "count": {"$sum": 1},
                    "total_amount": {"$sum": "$total_amount"}
                }
            },
            {
                "$group": {
                    "_id": "$_id.date",
                    "orders_by_status": {
                        "$push": {
                            "status": "$_id.status",
                            "count": "$count",
                            "amount": "$total_amount"
                        }
                    },
                    "total_revenue": {"$sum": "$total_amount"},
                    "total_orders": {"$sum": "$count"}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        result = await orders_collection.aggregate(pipeline).to_list(length=None)
        
        # Tạo dict để lookup
        revenue_dict = {}
        for item in result:
            revenue_dict[item["_id"]] = {
                "total_revenue": item["total_revenue"],
                "total_orders": item["total_orders"],
                "orders_by_status": item["orders_by_status"]
            }
        
        # Fill missing dates
        chart_data = []
        current = chart_start.replace(hour=0, minute=0, second=0, microsecond=0)
        while current <= chart_end:
            date_str = current.strftime("%Y-%m-%d")
            is_in_period = highlight_start <= current <= end_date
            
            if date_str in revenue_dict:
                data = revenue_dict[date_str]
                data_point = {
                    "date": date_str,
                    "total_revenue": data["total_revenue"],
                    "total_orders": data["total_orders"],
                    "avg_order_value": round(data["total_revenue"] / data["total_orders"], 2) if data["total_orders"] > 0 else 0,
                    "orders_by_status": data["orders_by_status"],
                    "is_current_period": is_in_period
                }
            else:
                data_point = {
                    "date": date_str,
                    "total_revenue": 0,
                    "total_orders": 0,
                    "avg_order_value": 0,
                    "orders_by_status": [],
                    "is_current_period": is_in_period
                }
            
            chart_data.append(data_point)
            current += timedelta(days=1)
        
        return {
            "title": "Phân tích doanh thu",
            "type": "bar",
            "color": "#059669",
            "data": chart_data,
            "metrics": ["total_revenue", "avg_order_value"]
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting revenue chart: {str(e)}")
        return {"title": "Revenue Analysis", "data": [], "error": str(e)}


@router.get("/metrics/{metric_type}", response_model=Dict[str, Any])
async def get_specific_metrics(
    metric_type: str,
    period: str = Query("all", description="Khoảng thời gian: today, week, month, year, all"),
    start_date: Optional[str] = Query(None, description="Ngày bắt đầu (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Ngày kết thúc (YYYY-MM-DD)"),
    company_id: Optional[str] = Query(None, description="Lọc theo company_id"),
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    """
    🎯 **API Lấy Metrics Cụ Thể**
    
    **Supported metric types:**
    - `bots`: Thống kê bot system
    - `social`: Thống kê social media
    - `customers`: Thống kê khách hàng
    - `orders`: Thống kê đơn hàng
    - `knowledge`: Thống kê kiến thức
    - `activities`: Thống kê hoạt động
    
    **Features:**
    - 📊 Chi tiết metrics theo từng loại
    - 📈 Dữ liệu tăng trưởng và so sánh
    - 🎯 Lọc theo thời gian và công ty
    - ⚡ Tối ưu performance chỉ query cần thiết
    """
    try:
        user_id = current_user.get("user_id")
        start_datetime, end_datetime = get_date_range(period, start_date, end_date)
        
        user_filter = {"user_id": user_id}
        if company_id:
            user_filter["company_id"] = company_id
        
        # Route to specific metric function
        metric_functions = {
            "bots": get_bot_metrics,
            "social": get_social_metrics,
            "customers": get_customer_metrics,
            "orders": get_order_metrics,
            "knowledge": get_knowledge_metrics,
            "activities": get_activity_metrics
        }
        
        if metric_type not in metric_functions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid metric type. Supported: {list(metric_functions.keys())}"
            )
        
        metric_data = await metric_functions[metric_type](factory, start_datetime, end_datetime, user_filter)
        
        return {
            "success": True,
            "data": {
                "metric_type": metric_type,
                "metrics": metric_data,
                "metadata": {
                    "period": period,
                    "start_date": start_datetime.strftime("%Y-%m-%d"),
                    "end_date": end_datetime.strftime("%Y-%m-%d"),
                    "user_id": user_id,
                    "company_id": company_id,
                    "generated_at": datetime.now().isoformat()
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting {metric_type} metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")


@router.get("/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(
    current_user: dict = Depends(get_current_user), 
    factory = Depends(get_management_factory)
):
    """
    📊 **Quick Stats Dashboard**
    
    Lấy số liệu thống kê nhanh toàn hệ thống của user hiện tại.
    Được tối ưu cho hiển thị widgets/cards trên dashboard.
    
    **Response bao gồm:**
    - 🔢 Tổng số records của từng loại
    - ⚡ Performance metrics
    - 🎯 Key indicators
    """
    try:
        user_id = current_user.get("user_id")
        user_filter = {"user_id": user_id}
        
        # Parallel count queries
        counts = await asyncio.gather(
            factory._db_manager.database["bots"].count_documents(user_filter),
            factory._db_manager.database["bots"].count_documents({**user_filter, "status": "on"}),
            factory._db_manager.database["social_accounts"].count_documents(user_filter),
            factory._db_manager.database["contacts"].count_documents(user_filter),
            factory._db_manager.database["orders"].count_documents(user_filter),
            factory._db_manager.database["documents"].count_documents(user_filter),
            factory._db_manager.database["histories"].count_documents(user_filter),
            factory._db_manager.database["feedback"].count_documents(user_filter)
        )
        
        total_bots, active_bots, social_accounts, customers, orders, documents, messages, feedback = counts
        
        return {
            "success": True,
            "data": {
                "bots": {
                    "total": total_bots,
                    "active": active_bots,
                    "inactive": total_bots - active_bots
                },
                "social": {
                    "accounts": social_accounts
                },
                "customers": {
                    "total": customers
                },
                "orders": {
                    "total": orders
                },
                "knowledge": {
                    "documents": documents
                },
                "activities": {
                    "messages": messages,
                    "feedback": feedback
                },
                "summary": {
                    "total_entities": total_bots + social_accounts + customers + orders + documents,
                    "total_interactions": messages + feedback,
                    "bot_utilization": (active_bots / total_bots * 100) if total_bots > 0 else 0
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stats error: {str(e)}")


# ==================== HELPER FUNCTIONS ====================

def serialize_document(doc: dict) -> dict:
    """Convert MongoDB document to JSON serializable format"""
    if not doc:
        return doc
    
    # Create a copy to avoid modifying original
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, dict):
            serialized[key] = serialize_document(value)
        elif isinstance(value, list):
            serialized[key] = [serialize_document(item) if isinstance(item, dict) else str(item) if isinstance(item, ObjectId) else item for item in value]
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def serialize_documents(docs: list) -> list:
    """Convert list of MongoDB documents to JSON serializable format"""
    return [serialize_document(doc) for doc in docs]


# End of dashboard API file



# End of dashboard API file
