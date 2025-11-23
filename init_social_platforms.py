"""
Script khởi tạo dữ liệu mặc định cho Social Media Management
"""

import asyncio
import sys
import os

# Thêm đường dẫn project vào sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.data.managements import get_mongodb_factory


async def init_default_socials():
    """Khởi tạo các social platforms mặc định"""
    print("🚀 Initializing default social platforms...")
    
    try:
        # Lấy management factory
        factory = get_mongodb_factory()
        
        # Danh sách social platforms mặc định
        default_socials = [
            {
                "name": "Facebook",
                "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/51/Facebook_f_logo_%282019%29.svg",
                "_id": "s_facebook"
            },
            {
                "name": "Instagram", 
                "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png",
                "_id": "s_instagram"
            },
            {
                "name": "Twitter",
                "logo_url": "https://upload.wikimedia.org/wikipedia/commons/6/6f/Logo_of_Twitter.svg",
                "_id": "s_twitter"
            },
            {
                "name": "LinkedIn",
                "logo_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png", 
                "_id": "s_linkedin"
            }
        ]
        
        for social_data in default_socials:
            try:
                # Kiểm tra xem social đã tồn tại chưa
                existing_social = await factory.social_manager.get_by_id(social_data["_id"])
                
                if existing_social:
                    print(f"✅ Social platform '{social_data['name']}' already exists")
                    # Cập nhật thông tin nếu cần
                    await factory.social_manager.update_by_id(
                        social_data["_id"],
                        {
                            "name": social_data["name"],
                            "logo_url": social_data["logo_url"]
                        }
                    )
                else:
                    # Tạo social platform mới với ID tùy chỉnh
                    result = await factory.social_manager.create({
                        "_id": social_data["_id"],
                        "name": social_data["name"],
                        "logo_url": social_data["logo_url"]
                    })
                    print(f"✅ Created social platform '{social_data['name']}' with ID: {social_data['_id']}")
                    
            except Exception as e:
                print(f"❌ Error processing social platform '{social_data['name']}': {e}")
        
        print("\n🎉 Default social platforms initialization completed!")
        
        # Hiển thị danh sách social platforms hiện tại
        all_socials = await factory.social_manager.get_all()
        print("\n📋 Current social platforms:")
        for social in all_socials:
            print(f"  - {social.get('name')} (ID: {social.get('_id')})")
        
    except Exception as e:
        print(f"❌ Error initializing default socials: {e}")


async def main():
    """Main function"""
    await init_default_socials()


if __name__ == "__main__":
    asyncio.run(main())
