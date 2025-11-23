"""
Example: Cách sử dụng Notification System
Các ví dụ thực tế để tích hợp notification vào ứng dụng
"""

from datetime import datetime, timedelta
from controllers.ultils.notification_helper import NotificationHelper, notify, notify_with_link
from controllers.data.managements.system_management import (
    NotificationCategory,
    NotificationType,
    NotificationAction
)


# ===== EXAMPLE 1: Social Media Connection =====
async def example_social_connection(user_id: str, platform: str, account_data: dict):
    """
    Gửi notification sau khi user kết nối social platform thành công
    """
    # Sử dụng pre-built function
    await NotificationHelper.notify_social_connected(
        user_id=user_id,
        platform=platform,
        account_name=account_data["name"],
        account_id=account_data["id"]
    )
    
    print(f"✅ Notification sent: {platform} connected successfully")


# ===== EXAMPLE 2: Facebook Page Added =====
async def example_page_added(user_id: str, page_data: dict):
    """
    Gửi notification khi thêm Facebook Page
    """
    await NotificationHelper.notify_page_added(
        user_id=user_id,
        platform="Facebook",
        page_name=page_data["name"],
        page_id=page_data["id"]
    )
    
    print(f"✅ Notification sent: Page '{page_data['name']}' added")


# ===== EXAMPLE 3: Bot Creation =====
async def example_bot_created(user_id: str, bot_name: str, bot_id: str):
    """
    Gửi notification khi tạo bot mới
    """
    await NotificationHelper.notify_bot_created(
        user_id=user_id,
        bot_name=bot_name,
        bot_id=bot_id
    )
    
    print(f"✅ Notification sent: Bot '{bot_name}' created")


# ===== EXAMPLE 4: New Message Received =====
async def example_new_message(
    page_owner_id: str,
    sender_name: str,
    message: str,
    conversation_id: str
):
    """
    Gửi notification khi nhận tin nhắn mới
    """
    await NotificationHelper.notify_new_message(
        user_id=page_owner_id,
        sender_name=sender_name,
        message_preview=message,
        conversation_id=conversation_id,
        platform="messenger"
    )
    
    print(f"✅ Notification sent: New message from {sender_name}")


# ===== EXAMPLE 5: Document Upload and Processing =====
async def example_document_workflow(user_id: str, file_name: str, file_size: int):
    """
    Workflow hoàn chỉnh: Upload -> Processing -> Complete
    """
    # Step 1: Document uploaded
    doc_id = "doc_12345"  # Giả sử đây là ID document vừa upload
    
    await NotificationHelper.notify_document_uploaded(
        user_id=user_id,
        document_name=file_name,
        document_id=doc_id,
        file_size=file_size
    )
    
    print(f"✅ Step 1: Document uploaded notification sent")
    
    # Step 2: Processing (simulate processing time)
    # ... xử lý document ...
    
    # Step 3: Processing completed
    chunks_count = 42  # Giả sử chia thành 42 chunks
    
    await NotificationHelper.notify_document_processed(
        user_id=user_id,
        document_name=file_name,
        document_id=doc_id,
        chunks_count=chunks_count
    )
    
    print(f"✅ Step 2: Document processed notification sent")


# ===== EXAMPLE 6: Custom Notification với Link =====
async def example_custom_notification_with_link(user_id: str):
    """
    Tạo notification tùy chỉnh với link reference
    """
    await notify_with_link(
        user_id=user_id,
        title="Lead mới từ Facebook",
        content="Bạn có một lead tiềm năng mới cần xem xét",
        link_type="lead",
        link_url="/crm/leads/lead_789",
        resource_id="lead_789",
        notification_type=NotificationType.INFO,
        category=NotificationCategory.CRM,
        action=NotificationAction.LEAD_CREATED,
        priority=4,
        metadata={
            "source": "facebook_messenger",
            "lead_score": 85,
            "estimated_value": 5000000
        }
    )
    
    print("✅ Custom notification with link sent")


# ===== EXAMPLE 7: Bulk Notification cho Multiple Users =====
async def example_bulk_notification(user_ids: list):
    """
    Gửi notification cho nhiều users cùng lúc (system announcement)
    """
    await NotificationHelper.notify_system_update(
        user_ids=user_ids,
        title="Tính năng mới: AI Assistant",
        content="Chúng tôi đã ra mắt tính năng AI Assistant với khả năng trả lời tự động thông minh hơn",
        priority=3
    )
    
    print(f"✅ Bulk notification sent to {len(user_ids)} users")


# ===== EXAMPLE 8: Maintenance Notification =====
async def example_maintenance_notification(user_ids: list):
    """
    Thông báo bảo trì hệ thống
    """
    maintenance_time = datetime.now() + timedelta(hours=2)  # Bảo trì sau 2 giờ
    
    await NotificationHelper.notify_maintenance(
        user_ids=user_ids,
        start_time=maintenance_time,
        duration_minutes=30
    )
    
    print(f"✅ Maintenance notification sent to {len(user_ids)} users")


# ===== EXAMPLE 9: Error Notification =====
async def example_error_notification(user_id: str, error_context: dict):
    """
    Gửi notification khi có lỗi xảy ra
    """
    await notify(
        user_id=user_id,
        title="Lỗi khi gửi tin nhắn",
        content=f"Không thể gửi tin nhắn đến {error_context['recipient']}. "
                f"Lỗi: {error_context['error_message']}",
        notification_type=NotificationType.ERROR,
        category=NotificationCategory.CONVERSATION,
        action=NotificationAction.MESSAGE_FAILED,
        priority=4,
        metadata={
            "error_code": error_context.get("error_code"),
            "timestamp": datetime.now().isoformat(),
            "conversation_id": error_context.get("conversation_id")
        }
    )
    
    print("✅ Error notification sent")


# ===== EXAMPLE 10: Payment Notification =====
async def example_payment_notification(user_id: str, payment_data: dict):
    """
    Notification cho thanh toán
    """
    if payment_data["status"] == "success":
        await NotificationHelper.notify_payment_success(
            user_id=user_id,
            amount=payment_data["amount"],
            currency=payment_data["currency"],
            transaction_id=payment_data["transaction_id"]
        )
        print("✅ Payment success notification sent")
    else:
        await NotificationHelper.notify_payment_failed(
            user_id=user_id,
            amount=payment_data["amount"],
            currency=payment_data["currency"],
            reason=payment_data["reason"]
        )
        print("✅ Payment failed notification sent")


# ===== EXAMPLE 11: Tích hợp vào API Endpoint =====
"""
# Trong file api/v1/socials/api_social_media.py

from controllers.ultils.notification_helper import NotificationHelper

@router.post("/socials/{social_id}/connect")
async def connect_social(
    social_id: str,
    current_user: dict = Depends(get_current_user),
    factory = Depends(get_management_factory)
):
    try:
        user_id = current_user.get("user_id")
        
        # Logic kết nối social platform
        result = await connect_facebook(authorization_code, user_id)
        
        # Gửi notification
        await NotificationHelper.notify_social_connected(
            user_id=user_id,
            platform="Facebook",
            account_name=result["account_name"],
            account_id=result["account_id"]
        )
        
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
"""


# ===== EXAMPLE 12: Background Task với Notification =====
"""
# Trong file bot/bot_facebook_messenger.py

from fastapi import BackgroundTasks
from controllers.ultils.notification_helper import NotificationHelper

async def process_message_with_notification(
    sender_id: str,
    page_id: str,
    message: str,
    page_owner_id: str
):
    # Xử lý tin nhắn
    response = await process_message(sender_id, page_id, message)
    
    # Gửi notification cho page owner
    await NotificationHelper.notify_new_message(
        user_id=page_owner_id,
        sender_name=sender_id,
        message_preview=message,
        conversation_id=f"conv_{sender_id}_{page_id}",
        platform="messenger"
    )
    
    return response

@router.post("/socials/facebook/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    # ... parse webhook data ...
    
    # Add notification task to background
    background_tasks.add_task(
        process_message_with_notification,
        sender_id=webhook_data.sender_id,
        page_id=webhook_data.page_id,
        message=webhook_data.content,
        page_owner_id=page_owner_id
    )
    
    return "EVENT_RECEIVED"
"""


# ===== EXAMPLE 13: Conditional Notification =====
async def example_conditional_notification(user_id: str, lead_data: dict):
    """
    Chỉ gửi notification nếu lead đủ important
    """
    lead_score = lead_data.get("score", 0)
    
    # Chỉ notify nếu lead score >= 70
    if lead_score >= 70:
        priority = 5 if lead_score >= 90 else 4
        
        await NotificationHelper.notify_lead_created(
            user_id=user_id,
            lead_name=lead_data["name"],
            lead_id=lead_data["id"],
            source=lead_data.get("source", "unknown")
        )
        
        print(f"✅ High-value lead notification sent (score: {lead_score})")
    else:
        print(f"ℹ️ Lead score too low ({lead_score}), no notification sent")


# ===== EXAMPLE 14: Notification với Expiration =====
async def example_time_sensitive_notification(user_ids: list):
    """
    Notification có thời gian hết hạn (ví dụ: flash sale)
    """
    expires_at = datetime.now() + timedelta(hours=24)  # Hết hạn sau 24h
    
    from controllers.data.managements import get_mongodb_factory
    factory = get_mongodb_factory()
    
    await factory.notification_manager.notify_multiple_users(
        user_ids=user_ids,
        title="🔥 Flash Sale 24h",
        content="Giảm giá 50% tất cả gói dịch vụ trong 24h. Không bỏ lỡ!",
        notification_type=NotificationType.ALERT,
        category=NotificationCategory.SUBSCRIPTION,
        action="flash_sale",
        priority=5,
        link={
            "type": "promotion",
            "url": "/pricing",
            "resource_id": "flash_sale_2025_10"
        },
        expires_at=expires_at
    )
    
    print(f"✅ Time-sensitive notification sent to {len(user_ids)} users")


# ===== EXAMPLE 15: Try-Catch Pattern =====
async def example_safe_notification(user_id: str):
    """
    Best practice: Không để notification failure ảnh hưởng main flow
    """
    try:
        # Main business logic (example)
        result = {"status": "success", "data": "operation completed"}
        
        # Try to send notification (non-critical)
        try:
            await NotificationHelper.notify(
                user_id=user_id,
                title="Operation completed",
                content="Your operation has been completed successfully",
                notification_type=NotificationType.SUCCESS,
                category=NotificationCategory.SYSTEM
            )
        except Exception as notification_error:
            # Log error but don't break the main flow
            print(f"⚠️ Failed to send notification: {str(notification_error)}")
        
        return result
        
    except Exception as e:
        # Handle main business logic error
        print(f"❌ Main operation failed: {str(e)}")
        raise


# ===== MAIN DEMO =====
async def main():
    """
    Run all examples
    """
    print("=" * 60)
    print("NOTIFICATION SYSTEM - EXAMPLES")
    print("=" * 60)
    
    user_id = "demo_user_123"
    
    # Example 1
    print("\n1. Social Connection:")
    await example_social_connection(
        user_id=user_id,
        platform="Facebook",
        account_data={"name": "John Doe", "id": "fb_acc_456"}
    )
    
    # Example 2
    print("\n2. Page Added:")
    await example_page_added(
        user_id=user_id,
        page_data={"name": "My Shop", "id": "fb_page_789"}
    )
    
    # Example 3
    print("\n3. Bot Created:")
    await example_bot_created(
        user_id=user_id,
        bot_name="Customer Support Bot",
        bot_id="bot_123"
    )
    
    # Example 4
    print("\n4. New Message:")
    await example_new_message(
        page_owner_id=user_id,
        sender_name="Nguyen Van A",
        message="Hello, I need help with your product",
        conversation_id="conv_456"
    )
    
    # Example 5
    print("\n5. Document Workflow:")
    await example_document_workflow(
        user_id=user_id,
        file_name="product_catalog.pdf",
        file_size=2048576
    )
    
    # Example 6
    print("\n6. Custom Notification:")
    await example_custom_notification_with_link(user_id=user_id)
    
    # Example 7
    print("\n7. Bulk Notification:")
    await example_bulk_notification(user_ids=[user_id, "user2", "user3"])
    
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
