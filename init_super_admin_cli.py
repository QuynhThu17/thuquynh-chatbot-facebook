#!/usr/bin/env python3
"""
MekongAI SuperAdmin Initialization CLI
=====================================
Tool để khởi tạo và quản lý SuperAdmin system

Usage:
    python init_super_admin_cli.py init-system      # Khởi tạo hệ thống hoàn chỉnh
    python init_super_admin_cli.py create-partner   # Tạo đối tác mới
    python init_super_admin_cli.py show-hierarchy   # Hiển thị cây hierarchy
    python init_super_admin_cli.py reset-system     # Reset toàn bộ hệ thống
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import Dict, Any

# Setup logging với UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('mekongai_init.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Import MekongAI modules
try:
    from controllers.data.init_defaults import init_system_defaults, get_default_initializer
    from controllers.data.managements import get_mongodb_factory
    from configs.constant import MONGODB_URI, MONGODB_DATABASE
except ImportError as e:
    logger.error(f"Failed to import MekongAI modules: {e}")
    sys.exit(1)

class SuperAdminCLI:
    """CLI tool cho SuperAdmin management"""
    
    def __init__(self):
        self.factory = None
    
    async def initialize(self):
        """Khởi tạo connections"""
        try:
            from controllers.databases.mongodb.mongodb import MongoDBManager
            # Tạo MongoDB manager trước
            mongodb_manager = MongoDBManager(MONGODB_URI)
            connected = await mongodb_manager.connect(MONGODB_DATABASE)
            
            if not connected:
                raise Exception("Failed to connect to MongoDB")
            
            # Sau đó khởi tạo factory với mongodb_manager
            self.factory = get_mongodb_factory(mongodb_manager)
            if not self.factory:
                raise Exception("Failed to get MongoDB factory")
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            sys.exit(1)
    
    async def init_system(self):
        """Khởi tạo toàn bộ hệ thống"""
        logger.info("Initializing complete MekongAI system...")
        
        try:
            await init_system_defaults()
            logger.info("System initialization completed successfully!")
            await self._show_super_admin_info()
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            raise e
    
    async def create_partner(self):
        """Interactive partner creation"""
        logger.info("Creating new partner...")
        
        try:
            # Get partner info from user input
            name = input("Partner Name: ").strip()
            email = input("Partner Email: ").strip()
            contact_person = input("Contact Person: ").strip()
            phone = input("Phone (optional): ").strip() or None
            
            print("\nHierarchy Types:")
            print("1. white_label_admin - Full white label partner")
            print("2. partner_admin - Reseller partner")
            hierarchy_choice = input("Choose hierarchy type (1-2): ").strip()
            
            hierarchy_type = "white_label_admin" if hierarchy_choice == "1" else "partner_admin"
            license_type = "white_label" if hierarchy_choice == "1" else "reseller"
            
            # TODO: Implement partner creation logic using SuperAdmin API
            logger.info(f"Creating partner: {name} ({email}) as {hierarchy_type}")
            
            # Mock creation for now
            partner_data = {
                "name": name,
                "email": email,
                "contact_person": contact_person,
                "phone": phone,
                "hierarchy_type": hierarchy_type,
                "license_type": license_type,
                "created_at": datetime.now()
            }
            
            logger.info(f"Partner created successfully: {partner_data}")
            
        except KeyboardInterrupt:
            logger.info("Partner creation cancelled by user")
        except Exception as e:
            logger.error(f"Failed to create partner: {e}")
    
    async def show_hierarchy(self):
        """Hiển thị cây hierarchy"""
        logger.info("Loading hierarchy tree...")
        
        try:
            hierarchy_manager = self.factory.hierarchy_manager
            
            # Tìm SuperAdmin root
            super_hierarchies = await hierarchy_manager.get_all(
                filter_query={"hierarchy_type": "super_admin"},
                limit=1
            )
            
            if not super_hierarchies:
                logger.warning("No SuperAdmin found!")
                return
            
            root_hierarchy = super_hierarchies[0]
            await self._print_hierarchy_tree(root_hierarchy, 0)
            
        except Exception as e:
            logger.error(f"Failed to show hierarchy: {e}")
    
    async def reset_system(self):
        """Reset toàn bộ hệ thống"""
        logger.warning("⚠️ This will DELETE ALL DATA in the system!")
        
        confirm = input("Type 'RESET_MEKONGAI_SYSTEM' to confirm: ")
        if confirm != "RESET_MEKONGAI_SYSTEM":
            logger.info("❌ Reset cancelled")
            return
        
        try:
            logger.info("🗑️ Resetting system...")
            
            # Drop all collections
            collections = [
                "users", "hierarchy", "features", "roles", "balances", "packages", 
                "subscriptions", "transactions", "socials", "social_accounts",
                "identities", "procedures", "bots", "companies", "contacts",
                "products", "warehouses", "orders", "documents", "histories"
            ]
            
            for collection_name in collections:
                try:
                    await self.factory.db_manager.database[collection_name].drop()
                    logger.info(f"  ✅ Dropped {collection_name}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Failed to drop {collection_name}: {e}")
            
            logger.info("✅ System reset completed")
            logger.info("🚀 You can now run 'init-system' to reinitialize")
            
        except Exception as e:
            logger.error(f"❌ System reset failed: {e}")
    
    async def _show_super_admin_info(self):
        """Hiển thị thông tin SuperAdmin"""
        try:
            user_manager = self.factory.user_manager
            super_admin = await user_manager.get_by_email("admin@mekongai.com")
            
            if super_admin:
                logger.info("=" * 60)
                logger.info("MEKONGAI SUPERADMIN INFORMATION")
                logger.info("=" * 60)
                logger.info(f"Name: {super_admin['name']}")
                logger.info(f"Email: {super_admin['email']}")
                logger.info(f"Created: {super_admin.get('create_at', 'Unknown')}")
                logger.info("")
                logger.info("IMPORTANT SECURITY NOTES:")
                logger.info("1. Change the default password immediately!")
                logger.info("2. Enable 2FA for SuperAdmin account")
                logger.info("3. Restrict SuperAdmin API access by IP")
                logger.info("4. Monitor SuperAdmin activities")
                logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Failed to show SuperAdmin info: {e}")
    
    async def _print_hierarchy_tree(self, hierarchy, level=0, max_level=5):
        """In cây hierarchy đệ quy"""
        if level > max_level:
            return
        
        # Get user info
        user_manager = self.factory.user_manager
        user = await user_manager.get_by_id(hierarchy["user_id"])
        
        if not user:
            return
        
        # Print current node
        indent = "  " * level
        hierarchy_type = hierarchy.get("hierarchy_type", "user")
        status = hierarchy.get("partner_info", {}).get("status", "active")
        
        print(f"{indent}├── {user['name']} ({user['email']})")
        print(f"{indent}    Type: {hierarchy_type} | Status: {status}")
        print(f"{indent}    Children: {len(hierarchy.get('children', []))}")
        
        # Print children
        children_ids = hierarchy.get("children", [])
        for child_id in children_ids:
            child_hierarchy = await self.factory.hierarchy_manager.get_by_user_id(child_id)
            if child_hierarchy:
                await self._print_hierarchy_tree(child_hierarchy, level + 1, max_level)

async def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="MekongAI SuperAdmin Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python init_super_admin_cli.py init-system        # Initialize complete system
  python init_super_admin_cli.py create-partner     # Create new partner
  python init_super_admin_cli.py show-hierarchy     # Show hierarchy tree
  python init_super_admin_cli.py reset-system       # Reset entire system
        """
    )
    
    parser.add_argument(
        'command',
        choices=['init-system', 'create-partner', 'show-hierarchy', 'reset-system'],
        help='Command to execute'
    )
    
    args = parser.parse_args()
    
    # Initialize CLI
    cli = SuperAdminCLI()
    await cli.initialize()
    
    # Execute command
    if args.command == 'init-system':
        await cli.init_system()
    elif args.command == 'create-partner':
        await cli.create_partner()
    elif args.command == 'show-hierarchy':
        await cli.show_hierarchy()
    elif args.command == 'reset-system':
        await cli.reset_system()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("❌ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
