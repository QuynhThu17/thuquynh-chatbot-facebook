"""
User Management API Endpoints
Cung cấp API cho users, hierarchy, features, roles, balances, packages, subscriptions, transactions
Updated with Authentication Integration and PayOS Payment System
"""

from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from configs.environment import get_vietnam_now_naive
from decimal import Decimal
import logging
import uuid

# Import managers
from controllers.data.managements import get_mongodb_factory
from controllers.data.init_defaults import get_default_initializer

# Import authentication middleware
from controllers.auth.auth_middleware import get_current_user, get_admin_user, get_optional_current_user

# Import PayOS
from payos import PayOS
from payos.types import CreatePaymentLinkRequest, ItemData
from configs import constant

logger = logging.getLogger(__name__)
router = APIRouter(tags=["User Management"])

# Initialize PayOS
payOS = PayOS(
    client_id=constant.PAYOS_CLIENT_ID,
    api_key=constant.PAYOS_API_KEY,
    checksum_key=constant.PAYOS_CHECKSUM_KEY
)

# Pydantic Models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: Optional[str] = None
    method: str = "email_password"  # email_password, google
    avatar_url: Optional[str] = None
    roles: Optional[List[str]] = []

class UserUpdate(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    roles: Optional[List[str]] = None

class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    method: str
    google_id: Optional[str] = None
    avatar_url: Optional[str] = None
    roles: List[str] = []
    create_at: datetime
    update_at: datetime

class EmailVerify(BaseModel):
    email: str

class HierarchyCreate(BaseModel):
    user_id: str
    parent: Optional[str] = None
    children: Optional[List[str]] = []

class FeatureCreate(BaseModel):
    name: str
    description: Optional[str] = None

class RoleCreate(BaseModel):
    name: str
    permissions: Optional[List[str]] = []

class PackageCreate(BaseModel):
    name: str
    price: float
    duration_months: int
    description: Optional[str] = None

class SubscriptionCreate(BaseModel):
    user_id: str
    package_id: str
    duration_months: int = 1
    is_auto_renew: bool = False

class TransactionCreate(BaseModel):
    user_id: str
    type: str  # purchase_package, usage, refund
    amount: float
    description: Optional[str] = None

class PurchasePackageRequest(BaseModel):
    package_id: str
    duration_months: int = 1
    is_auto_renew: bool = False
    cancel_url: Optional[str] = None
    return_url: Optional[str] = None
    
class PaymentResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str

class PaymentStatusRequest(BaseModel):
    order_id: str

class DepositRequest(BaseModel):
    amount: float
    description: Optional[str] = "Nạp tiền vào tài khoản"

class UpdateUsageRequest(BaseModel):
    limit_type: str  # messages_per_month, social, bot, etc.
    usage_amount: int = 1
    operation: str = "add"  # add or set

class LimitsResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    message: str

# Dependency to get management factory
# def get_management_factory():
#     return get_mongodb_factory()

# Dependency to get management factory
def get_management_factory():
    """Get initialized management factory"""
    try:
        factory = get_mongodb_factory()
        if factory is None:
            raise HTTPException(status_code=503, detail="MongoDB Management Factory not initialized")
        return factory
    except Exception as e:
        logger.error(f"Failed to get management factory: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


# PayOS Helper Functions
async def create_payment_link(amount: float, order_code: str, cancel_url: str = None, return_url: str = None):
    """Tạo link thanh toán PayOS với URL cố định"""
    try:
        # URL cố định cho PayOS callback
        if not cancel_url:
            cancel_url = "https://mekongai.net/payment/payment-fail/"
        if not return_url:
            return_url = f"{constant.SERVER_ADDRESS}/api/v1/packages/purchase/status?order_id={order_code}"

        payment_data = CreatePaymentLinkRequest(
            orderCode=int(order_code),
            amount=int(amount),  # PayOS requires integer
            description="MEAI",
            cancelUrl=cancel_url,
            returnUrl=return_url
        )
        payment_link_data = payOS.createPaymentLink(paymentData=payment_data)

        if not payment_link_data:
            logger.error("createPaymentLink did not return valid data")
            return None
        return payment_link_data
    except Exception as e:
        logger.error(f'Error in create_payment_link: {e}')
        return None


async def check_transaction_in_db(order_id: str, factory):
    """Kiểm tra transaction trong database"""
    try:
        # Tìm transaction với order_id đã cho
        transactions = await factory.transaction_manager.get_all(
            filter_query={"order_id": order_id},
            limit=1
        )
        
        if transactions:
            return {"status": transactions[0].get("status")}
        return None  # Nếu không tồn tại, trả về None

    except Exception as e:
        logger.error(f"Error checking transaction: {e}")
        return None


async def process_payment_status(order_id: str, user_id: str, factory):
    """Kiểm tra và xử lý trạng thái thanh toán"""
    try:
        # Kiểm tra PayOS status trước
        payment_info = payOS.getPaymentLinkInformation(orderId=order_id)
        if not payment_info:
            return {"error": "Payment information not found"}

        # Kiểm tra transaction hiện tại trong DB
        existing_transaction = await check_transaction_in_db(order_id, factory)
        
        # Nếu PayOS trả về PAID nhưng DB chưa có hoặc vẫn pending, cập nhật DB
        if payment_info.status == "PAID":
            if not existing_transaction or existing_transaction.get("status") != "PAID":
                # Cập nhật transaction
                result = await save_transaction(
                    user_id=user_id,
                    order_id=order_id,
                    amount=payment_info.amount,
                    transaction_type="deposit",
                    payment_method="PayOS",
                    created_at=payment_info.createdAt,
                    status="PAID",
                    factory=factory
                )
                if result is None:
                    return {"error": "Failed to save transaction"}
                if result == 404:
                    return {"message": "User ID not found", "status": 404}
            return {"status": "PAID"}
        elif payment_info.status == "PENDING":
            return {"status": "PENDING"}
        else:
            return {"status": payment_info.status}
    except Exception as e:
        logger.error(f'Error processing payment: {e}')
        return {"error": f"Internal server error: {str(e)}"}


async def save_transaction(user_id: str, order_id: str, amount: float, 
                         transaction_type: str, payment_method: str, 
                         created_at: str, status: str, factory):
    """Lưu transaction và cập nhật balance hoặc subscription"""
    try:
        # Kiểm tra user tồn tại
        user = await factory.user_manager.get_by_id(user_id)
        if not user:
            logger.error("User ID không tồn tại.")
            return 404

        # Tìm pending transaction với order_id này
        pending_transactions = await factory.transaction_manager.get_all(
            filter_query={"order_id": order_id, "type": {"$regex": "^pending"}},
            limit=1
        )
        
        if pending_transactions:
            pending_transaction = pending_transactions[0]
            transaction_type_original = pending_transaction.get("type", "")
            package_id = pending_transaction.get("package_id")
            
            # Nếu là package purchase, tạo subscription và cập nhật package/limits cho user
            if "package_purchase" in transaction_type_original and package_id:
                package = await factory.package_manager.get_by_id(package_id)
                if package:
                    # Kiểm tra xem đã có subscription cho order này chưa
                    existing_subscriptions = await factory.subscription_manager.get_all(
                        filter_query={
                            "user_id": user_id,
                            "package_id": package_id,
                            "order_id": order_id
                        },
                        limit=1
                    )
                    
                    if not existing_subscriptions:
                        # Tạo subscription cho user với order_id để tránh duplicate
                        subscription = await factory.subscription_manager.create_subscription(
                            user_id=user_id,
                            package_id=package_id,
                            duration_months=package.get("duration_months", 1),
                            is_auto_renew=False
                        )
                        
                        # Cập nhật subscription với order_id
                        if subscription:
                            await factory.subscription_manager.update_by_id(
                                subscription["_id"],
                                {"order_id": order_id}
                            )
                    
                    # Cập nhật package hiện tại cho user
                    duration = package.get("duration_months", 1)
                    package_expires_at = get_vietnam_now_naive() + timedelta(days=duration * 30)
                    
                    # Khởi tạo limits cho user dựa trên package
                    package_limits = package.get("limits", {})
                    user_limits = {}
                    for limit_key, limit_value in package_limits.items():
                        user_limits[limit_key] = {
                            "total": limit_value,  # Giới hạn tối đa
                            "used": 0,            # Đã sử dụng (reset về 0)
                            "remaining": limit_value if limit_value != -1 else -1  # Còn lại (-1 = unlimited)
                        }
                    
                    # ✅ Cập nhật package, features và limits cho user
                    await factory.user_manager.update_by_id(user_id, {
                        "packages": package_id,
                        "current_package": package_id,
                        "package_name": package.get("name"),
                        "package_expires_at": package_expires_at,
                        "features": package.get("features", {}),  # ✅ Copy features
                        "limits": user_limits
                    })
                    
                    # ✅ Nếu là custom package, thêm user_id vào target_users của package
                    package_type = package.get("type", "default")
                    target_users = package.get("target_users", [])
                    
                    # Danh sách default system packages (không track target_users)
                    system_packages = ["p_free_trial", "p_basic", "p_professional", "p_enterprise"]
                    is_system_package = package_id in system_packages
                    
                    # Chỉ track target_users cho NON-SYSTEM packages (custom packages)
                    if not is_system_package:
                        if user_id not in target_users:
                            target_users.append(user_id)
                            # ✅ Update trực tiếp collection vì package_id là string custom
                            await factory.package_manager.collection.update_one(
                                {"_id": package_id},
                                {"$set": {
                                    "target_users": target_users,
                                    "type": "custom",
                                    "update_at": get_vietnam_now_naive()
                                }}
                            )
                            logger.info(f"✅ Added user {user_id} to custom package {package_id} target_users")
                    
                    logger.info(f"Updated package and limits for user {user_id}: {package.get('name')} - Package expires at: {package_expires_at}")
                    
                    # Update transaction type
                    transaction_type = "package_purchase"
                    description = f"Package purchase completed - {package.get('name', 'Unknown Package')}"
                else:
                    transaction_type = "deposit"
                    description = f"Payment via {payment_method} - Order: {order_id}"
            else:
                # Là deposit thông thường - cập nhật balance
                balance = await factory.balance_manager.get_by_user_id(user_id)
                if not balance:
                    # Tạo balance mới nếu chưa có
                    await factory.balance_manager.create_balance(user_id, amount)
                else:
                    # Cập nhật balance hiện có
                    await factory.balance_manager.update_balance(user_id, amount, "add")
                
                transaction_type = "deposit"
                description = f"Deposit via {payment_method} - Order: {order_id}"
                
            # Cập nhật pending transaction thành completed
            await factory.transaction_manager.update_by_id(
                pending_transaction["_id"],
                {
                    "type": transaction_type,
                    "status": status,
                    "payment_method": payment_method,
                    "payment_created_at": created_at,
                    "description": description,
                    "completed_at": get_vietnam_now_naive()
                }
            )
            
            logger.info("Giao dịch đã được cập nhật trong cơ sở dữ liệu.")
            return pending_transaction
        else:
            # Tạo transaction mới (fallback)
            new_transaction = await factory.transaction_manager.create_transaction(
                user_id=user_id,
                transaction_type=transaction_type,
                amount=amount,
                description=f"Payment via {payment_method} - Order: {order_id}"
            )
            
            # Thêm thông tin PayOS vào transaction
            await factory.transaction_manager.update_by_id(
                new_transaction["_id"],
                {
                    "order_id": order_id,
                    "payment_method": payment_method,
                    "payment_created_at": created_at,
                    "status": status
                }
            )
            
            logger.info("Giao dịch mới đã được tạo trong cơ sở dữ liệu.")
            return new_transaction
            
    except Exception as e:
        logger.error(f"Lỗi khi lưu giao dịch: {e}")
        return None
    
    
@router.put("/users", response_model=Dict[str, Any])
async def update_user(
    user_data: UserUpdate, 
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Cập nhật thông tin user"""
    try:
        # Kiểm tra quyền: admin hoặc chính user đó
        is_admin = "admin" in current_user.get("roles", []) or "super_admin" in current_user.get("roles", [])
        is_same_user = current_user.get("user_id")
        user_id = current_user.get("user_id")
        
        if not (is_admin or is_same_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Nếu không phải admin, không cho phép thay đổi roles
        if not is_admin and user_data.roles is not None:
            raise HTTPException(status_code=403, detail="Only admin can change user roles")
        
        # Chỉ update các field không None
        update_data = {k: v for k, v in user_data.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No data to update")
        
        user = await factory.user_manager.update_by_id(user_id, update_data)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"success": True, "data": user}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# @router.delete("/users", response_model=Dict[str, Any])
# async def delete_user(
#     factory = Depends(get_management_factory),
#     current_user: dict = Depends(get_admin_user)
# ):
#     """Xóa user - Chỉ admin mới được"""
#     try:
#         user_id = current_user.get("user_id")
#         success = await factory.user_manager.delete_by_id(user_id)
#         if not success:
#             raise HTTPException(status_code=404, detail="User not found")
        
#         return {"success": True, "message": "User deleted successfully"}
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error deleting user: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

@router.get("/features", response_model=Dict[str, Any])
async def get_features(factory = Depends(get_management_factory)):
    """Lấy danh sách features"""
    try:
        features = await factory.feature_manager.get_all()
        return {"success": True, "data": features}
        
    except Exception as e:
        logger.error(f"Error getting features: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/roles", response_model=Dict[str, Any])
async def get_roles(factory = Depends(get_management_factory)):
    """Lấy danh sách roles"""
    try:
        roles = await factory.role_manager.get_all()
        return {"success": True, "data": roles}
        
    except Exception as e:
        logger.error(f"Error getting roles: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/packages", response_model=Dict[str, Any])
async def get_packages(
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """
    Lấy danh sách packages với filtering thông minh
    
    **Authentication**: Required (JWT Token)
    
    **Logic**:
    - User thường: Trả về tất cả packages type="default"
    - User có custom package: Trả về packages "default" (KHÔNG bao gồm p_enterprise) + custom packages của user
    
    **Response**:
    ```json
    {
        "success": true,
        "data": [
            {
                "_id": "package_id",
                "package_id": "p_starter",
                "name": "Starter",
                "price": 99000,
                "type": "default",
                ...
            }
        ]
    }
    ```
    
    **Changelog**: 
    - v2.0 (2025-10-08): Thêm authentication, smart filtering cho custom packages
    - v1.0: API gốc không cần auth
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token")
        
        # Lấy thông tin user để biết current_package
        user = await factory.user_manager.get_by_id(user_id)
        user_current_package = user.get("current_package") if user else None
        
        # Lấy tất cả packages active
        all_packages = await factory.package_manager.get_active_packages()
        
        # Kiểm tra xem user có package custom không
        has_custom_package = False
        custom_package_obj = None
        
        if user_current_package:
            # Tìm package hiện tại của user
            for pkg in all_packages:
                if pkg.get("_id") == user_current_package:
                    # Check nếu đây là custom package (có target_users hoặc type="custom")
                    target_users = pkg.get("target_users", [])
                    pkg_type = pkg.get("type", "default")
                    
                    if (target_users and user_id in target_users) or pkg_type == "custom":
                        has_custom_package = True
                        custom_package_obj = pkg
                        break
        
        # Filter packages theo logic
        if has_custom_package and custom_package_obj:
            # User có custom package: Lấy default packages (trừ p_enterprise) + custom package của user
            filtered_packages = []
            
            for pkg in all_packages:
                package_id = pkg.get("_id", "")
                pkg_type = pkg.get("type", "default")
                
                # Bỏ qua p_enterprise khi user có custom package
                if package_id == "p_enterprise":
                    logger.debug(f"Skipping p_enterprise for user {user_id} with custom package")
                    continue
                
                # Lấy packages type="default"
                if pkg_type == "default":
                    filtered_packages.append(pkg)
                    logger.debug(f"Added default package: {package_id}")
            
            # Thêm custom package của user
            if custom_package_obj not in filtered_packages:
                filtered_packages.append(custom_package_obj)
                logger.debug(f"Added custom package: {custom_package_obj.get('_id')}")
            
            logger.info(f"User {user_id} has custom package {user_current_package}, filtered out p_enterprise. Total packages: {len(filtered_packages)}")
            
        else:
            # User thường: Lấy tất cả packages type="default"
            filtered_packages = [
                pkg for pkg in all_packages 
                if pkg.get("type", "default") == "default"
            ]
            logger.info(f"User {user_id} has no custom package, showing all default packages")
        
        # Sắp xếp packages theo thứ tự: p_free_trial -> p_pro -> p_business -> p_enterprise -> custom
        package_order = {
            "p_free_trial": 1,
            "p_pro": 2,
            "p_business": 3,
            "p_enterprise": 4
        }
        
        def sort_key(pkg):
            pkg_id = pkg.get("_id", "")
            # Nếu là package trong danh sách order, trả về thứ tự
            if pkg_id in package_order:
                return (package_order[pkg_id], pkg_id)
            # Custom packages sẽ được sắp xếp sau cùng theo tên
            return (999, pkg_id)
        
        filtered_packages.sort(key=sort_key)
        
        return {"success": True, "data": filtered_packages}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting packages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/packages/purchase", response_model=Dict[str, Any])
async def purchase_package(
    package_request: PurchasePackageRequest,
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Tạo link thanh toán cho package"""
    try:
        logger.info(package_request)
        
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token")
        
        # Lấy thông tin package
        package = await factory.package_manager.get_by_id(package_request.package_id)
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")
        
        # Sử dụng discounted_price nếu có, ngược lại dùng price
        amount = package.get("discounted_price", package.get("price", 0))
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Invalid package price")
        
        # Tạo order_code trước
        order_code = int(get_vietnam_now_naive().timestamp() * 1000)
        
        # Tạo payment link với order_code
        payment_link_data = await create_payment_link(amount, order_code, package_request.cancel_url, package_request.return_url)
        
        if not payment_link_data:
            raise HTTPException(status_code=500, detail="Failed to create payment link")
        
        # Lưu pending transaction với package info
        transaction = await factory.transaction_manager.create_transaction(
            user_id=user_id,
            transaction_type="pending_package_purchase",
            amount=amount,
            description=f"Pending package purchase - {package.get('name', 'Unknown Package')}"
        )
        
        # Update transaction với thông tin package và order
        await factory.transaction_manager.update_by_id(
            transaction["_id"],
            {
                "package_id": package_request.package_id,
                "package_name": package.get("name"),
                "order_id": str(order_code),  # Lưu dưới dạng string
                "payment_method": "PayOS"
            }
        )
        
        return {
            "success": True,
            "data": {
                "checkout_url": payment_link_data.checkoutUrl,
                "order_code": order_code,
                "qr_code": payment_link_data.qrCode,
                "package": {
                    "id": package_request.package_id,
                    "name": package.get("name"),
                    "price": package.get("price"),
                    "discounted_price": package.get("discounted_price"),
                    "final_amount": amount,
                    "duration_months": package.get("duration_months")
                },
                "transaction_id": str(transaction["_id"]),
                "cancel_url": package_request.cancel_url,
                "return_url": package_request.return_url
            },
            "message": "Package payment link created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purchasing package: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/packages/purchase/status", response_model=Dict[str, Any])
async def get_package_purchase_status(
    order_id: str = Query(..., description="Order ID to check status"),
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_optional_current_user)
):
    """Kiểm tra trạng thái mua package theo order_id"""
    try:
        # Tìm transaction với order_id này trước
        transactions = await factory.transaction_manager.get_all(
            filter_query={"order_id": order_id},
            limit=1
        )
        
        if not transactions:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        transaction = transactions[0]
        user_id = transaction.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in transaction")
        
        # Nếu có current_user, kiểm tra quyền truy cập
        if current_user:
            current_user_id = current_user.get("user_id")
            is_admin = "admin" in current_user.get("roles", []) or "super_admin" in current_user.get("roles", [])
            
            if not (is_admin or current_user_id == user_id):
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Kiểm tra payment status từ PayOS
        payment_status_result = await process_payment_status(order_id, user_id, factory)
        logger.info(f"Payment status result for order {order_id}: {payment_status_result}")
        
        response_data = {
            "order_id": order_id,
            "transaction_id": str(transaction.get("_id")),
            "transaction_type": transaction.get("type"),
            "amount": transaction.get("amount"),
            "package_id": transaction.get("package_id"),
            "package_name": transaction.get("package_name"),
            "payment_status": payment_status_result.get("status", "UNKNOWN"),
            "created_at": transaction.get("create_at"),
            "subscription_created": False,
            "subscription_id": None
        }
        
        # Nếu đã thanh toán thành công, check subscription
        if payment_status_result.get("status") == "PAID":
            package_id = transaction.get("package_id")
            if package_id:
                # Tìm subscription tương ứng
                subscriptions = await factory.subscription_manager.get_all(
                    filter_query={
                        "user_id": user_id,
                        "package_id": package_id,
                        "order_id": order_id
                    },
                    limit=1
                )
                
                if subscriptions:
                    subscription = subscriptions[0]
                    response_data.update({
                        "subscription_created": True,
                        "subscription_id": str(subscription.get("_id")),
                        "subscription_start_date": subscription.get("start_date"),
                        "subscription_end_date": subscription.get("end_date"),
                        "subscription_status": subscription.get("status")
                    })
        
        return {
            "success": True,
            "data": response_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting package purchase status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscriptions", response_model=Dict[str, Any])
async def get_user_subscriptions(
    status: Optional[str] = None, 
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Lấy subscriptions của user hiện tại"""
    try:
        user_id = current_user["user_id"]
        subscriptions = await factory.subscription_manager.get_by_user_id(user_id, status)
        
        # Enrich subscriptions with package information
        enriched_subscriptions = []
        for subscription in subscriptions:
            package_id = subscription.get("package_id")
            if package_id:
                package = await factory.package_manager.get_by_id(package_id)
                subscription["package_details"] = package
            enriched_subscriptions.append(subscription)
        
        return {"success": True, "data": enriched_subscriptions}
        
    except Exception as e:
        logger.error(f"Error getting subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/transactions", response_model=Dict[str, Any])
async def get_user_transactions(
    transaction_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Lấy transactions của user hiện tại với pagination"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token")
            
        transactions = await factory.transaction_manager.get_by_user_id(user_id, transaction_type)
        
        # Simple pagination
        total = len(transactions)
        paginated_transactions = transactions[skip:skip+limit]
        
        return {
            "success": True,
            "data": paginated_transactions,
            "pagination": {
                "skip": skip,
                "limit": limit,
                "total": total
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/limits", response_model=LimitsResponse)
async def get_user_limits(
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Lấy thông tin limits hiện tại của user"""
    try:
        user_id = current_user.get("user_id")
        user = await factory.user_manager.get_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        limits = user.get("limits", {})
        current_package = user.get("current_package")
        package_expires_at = user.get("package_expires_at")
        
        return LimitsResponse(
            success=True,
            data={
                "limits": limits,
                "current_package": current_package,
                "package_name": user.get("package_name"),
                "package_expires_at": package_expires_at
            },
            message="User limits retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user limits: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# @router.post("/limits/update-usage", response_model=Dict[str, Any])
# async def update_user_usage(
#     usage_data: UpdateUsageRequest,
#     factory = Depends(get_management_factory),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Cập nhật usage của user cho một limit cụ thể"""
#     try:
#         user_id = current_user.get("user_id")
#         user = await factory.user_manager.get_by_id(user_id)
        
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
            
#         limits = user.get("limits", {})
#         limit_type = usage_data.limit_type
        
#         if limit_type not in limits:
#             raise HTTPException(status_code=400, detail=f"Limit type '{limit_type}' not found")
            
#         limit_info = limits[limit_type]
#         total_limit = limit_info.get("total", 0)
#         current_used = limit_info.get("used", 0)
        
#         # Cập nhật usage
#         if usage_data.operation == "add":
#             new_used = current_used + usage_data.usage_amount
#         elif usage_data.operation == "set":
#             new_used = usage_data.usage_amount
#         else:
#             raise HTTPException(status_code=400, detail="Operation must be 'add' or 'set'")
            
#         # Kiểm tra không vượt quá limit (trừ trường hợp unlimited = -1)
#         if total_limit != -1 and new_used > total_limit:
#             raise HTTPException(
#                 status_code=400, 
#                 detail=f"Usage would exceed limit. Current: {current_used}, Limit: {total_limit}, Requested: {new_used}"
#             )
            
#         # Tính toán remaining
#         new_remaining = total_limit - new_used if total_limit != -1 else -1
        
#         # Cập nhật limit info
#         limits[limit_type] = {
#             "total": total_limit,
#             "used": new_used,
#             "remaining": new_remaining
#         }
        
#         # Lưu vào database
#         await factory.user_manager.update_by_id(user_id, {"limits": limits})
        
#         return {
#             "success": True,
#             "data": {
#                 "limit_type": limit_type,
#                 "previous_used": current_used,
#                 "new_used": new_used,
#                 "total": total_limit,
#                 "remaining": new_remaining
#             },
#             "message": f"Usage updated successfully for {limit_type}"
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error updating user usage: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/limits/check", response_model=Dict[str, Any])
# async def check_user_limit(
#     limit_type: str,
#     required_amount: int = 1,
#     factory = Depends(get_management_factory),
#     current_user: dict = Depends(get_current_user)
# ):
#     """Kiểm tra xem user có thể sử dụng thêm không"""
#     try:
#         user_id = current_user.get("user_id")
#         user = await factory.user_manager.get_by_id(user_id)
        
#         if not user:
#             raise HTTPException(status_code=404, detail="User not found")
            
#         limits = user.get("limits", {})
        
#         if limit_type not in limits:
#             return {
#                 "success": False,
#                 "can_use": False,
#                 "message": f"Limit type '{limit_type}' not found"
#             }
            
#         limit_info = limits[limit_type]
#         total_limit = limit_info.get("total", 0)
#         current_used = limit_info.get("used", 0)
        
#         # Nếu unlimited
#         if total_limit == -1:
#             return {
#                 "success": True,
#                 "can_use": True,
#                 "data": {
#                     "limit_type": limit_type,
#                     "total": "unlimited",
#                     "used": current_used,
#                     "remaining": "unlimited",
#                     "required": required_amount
#                 },
#                 "message": "Unlimited usage available"
#             }
            
#         # Kiểm tra còn đủ không
#         remaining = total_limit - current_used
#         can_use = remaining >= required_amount
        
#         return {
#             "success": True,
#             "can_use": can_use,
#             "data": {
#                 "limit_type": limit_type,
#                 "total": total_limit,
#                 "used": current_used,
#                 "remaining": remaining,
#                 "required": required_amount
#             },
#             "message": "Limit check completed"
#         }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Error checking user limit: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/package/status", response_model=Dict[str, Any])
async def get_package_status(
    factory = Depends(get_management_factory),
    current_user: dict = Depends(get_current_user)
):
    """Lấy thông tin package hiện tại của user"""
    try:
        user_id = current_user.get("user_id")
        user = await factory.user_manager.get_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        current_package = user.get("current_package")
        package_expires_at = user.get("package_expires_at")
        
        # Kiểm tra xem package có hết hạn không
        is_expired = False
        if package_expires_at:
            is_expired = get_vietnam_now_naive() > package_expires_at
            
        package_info = None
        if current_package:
            package_info = await factory.package_manager.get_by_id(current_package)
            
        return {
            "success": True,
            "data": {
                "current_package": current_package,
                "package_name": user.get("package_name"),
                "package_expires_at": package_expires_at,
                "is_expired": is_expired,
                "package_info": package_info,
                "limits": user.get("limits", {})
            },
            "message": "Package status retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting package status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
