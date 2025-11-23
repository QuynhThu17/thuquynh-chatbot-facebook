#!/usr/bin/env python3
"""
CLI Script để khởi tạo dữ liệu mặc định
Sử dụng: python init_defaults_cli.py [command] [options]
"""

import asyncio
import argparse
import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controllers.data.init_defaults import (
    get_default_initializer,
    init_system_defaults,
    init_user_defaults,
    reset_system_defaults,
    check_system_health
)
from controllers.databases.mongodb.mongodb import MongoDBManager
from configs.constant import MONGODB_URI, MONGODB_DATABASE

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class DefaultsCliManager:
    """CLI Manager cho việc khởi tạo dữ liệu mặc định"""
    
    def __init__(self):
        self.mongodb_manager = None
        
    async def _setup_connection(self):
        """Thiết lập kết nối database"""
        if not self.mongodb_manager:
            self.mongodb_manager = MongoDBManager(MONGODB_URI)
            connected = await self.mongodb_manager.connect(MONGODB_DATABASE)
            if not connected:
                logger.error("❌ Cannot connect to MongoDB")
                return False
            logger.info("✅ Connected to MongoDB")
            return True
        return True

    async def init_system(self, force: bool = False):
        """Khởi tạo dữ liệu mặc định cho hệ thống"""
        logger.info("🚀 Starting system initialization...")
        
        if not await self._setup_connection():
            return False
            
        try:
            if force:
                logger.info("⚠️ Force mode: Resetting existing data...")
                await reset_system_defaults()
            else:
                await init_system_defaults()
            
            logger.info("✅ System initialization completed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization failed: {str(e)}")
            return False

    async def init_user(self, user_id: str):
        """Khởi tạo dữ liệu mặc định cho user"""
        logger.info(f"🚀 Starting user initialization for: {user_id}")
        
        if not await self._setup_connection():
            return False
            
        try:
            await init_user_defaults(user_id)
            logger.info(f"✅ User initialization completed for: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ User initialization failed: {str(e)}")
            return False

    async def reset_system(self):
        """Reset tất cả dữ liệu mặc định của hệ thống"""
        logger.info("🔄 Starting system reset...")
        
        if not await self._setup_connection():
            return False
            
        try:
            await reset_system_defaults()
            logger.info("✅ System reset completed!")
            return True
            
        except Exception as e:
            logger.error(f"❌ System reset failed: {str(e)}")
            return False

    async def check_health(self):
        """Kiểm tra tình trạng hệ thống"""
        logger.info("🔍 Checking system health...")
        
        if not await self._setup_connection():
            return False
            
        try:
            health_report = await check_system_health()
            
            # In báo cáo
            print("\n" + "="*60)
            print("📊 SYSTEM HEALTH REPORT")
            print("="*60)
            
            all_ok = True
            for collection_name, info in health_report.items():
                status_icon = "✅" if info["count"] > 0 else "⚠️" if "Missing" in info["status"] else "❌"
                print(f"{status_icon} {info['name']}: {info['count']} records")
                if info["count"] == 0:
                    all_ok = False
            
            print("="*60)
            if all_ok:
                print("🎉 All systems are healthy!")
            else:
                print("⚠️ Some default data is missing. Consider running 'init-system'")
            print("="*60 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {str(e)}")
            return False

    async def interactive_menu(self):
        """Menu tương tác cho người dùng"""
        while True:
            print("\n" + "="*50)
            print("🔧 MekongAI Default Data Manager")
            print("="*50)
            print("1. Initialize System Defaults")
            print("2. Initialize User Defaults")
            print("3. Reset System Defaults")
            print("4. Check System Health")
            print("5. Exit")
            print("="*50)
            
            choice = input("Please select an option (1-5): ").strip()
            
            if choice == "1":
                force = input("Force reset existing data? (y/N): ").strip().lower() == 'y'
                await self.init_system(force)
                
            elif choice == "2":
                user_id = input("Enter User ID: ").strip()
                if user_id:
                    await self.init_user(user_id)
                else:
                    print("❌ User ID is required!")
                    
            elif choice == "3":
                confirm = input("Are you sure you want to reset all system defaults? (y/N): ").strip().lower()
                if confirm == 'y':
                    await self.reset_system()
                else:
                    print("❌ Reset cancelled!")
                    
            elif choice == "4":
                await self.check_health()
                
            elif choice == "5":
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid option! Please try again.")

    async def cleanup(self):
        """Dọn dẹp kết nối"""
        if self.mongodb_manager:
            await self.mongodb_manager.disconnect()
            logger.info("✅ MongoDB connection closed")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="MekongAI Default Data Initializer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python init_defaults_cli.py init-system                    # Initialize system defaults
  python init_defaults_cli.py init-system --force           # Force reset and initialize
  python init_defaults_cli.py init-user 12345               # Initialize defaults for user 12345
  python init_defaults_cli.py reset                         # Reset all system defaults  
  python init_defaults_cli.py health                        # Check system health
  python init_defaults_cli.py interactive                   # Interactive menu
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Init system command
    init_sys_parser = subparsers.add_parser('init-system', help='Initialize system defaults')
    init_sys_parser.add_argument('--force', action='store_true', 
                                help='Force reset existing data before initialization')
    
    # Init user command  
    init_user_parser = subparsers.add_parser('init-user', help='Initialize user defaults')
    init_user_parser.add_argument('user_id', help='User ID to initialize defaults for')
    
    # Reset command
    subparsers.add_parser('reset', help='Reset all system defaults')
    
    # Health check command
    subparsers.add_parser('health', help='Check system health')
    
    # Interactive command
    subparsers.add_parser('interactive', help='Launch interactive menu')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    cli_manager = DefaultsCliManager()
    
    try:
        if args.command == 'init-system':
            success = await cli_manager.init_system(force=args.force)
            
        elif args.command == 'init-user':
            success = await cli_manager.init_user(args.user_id)
            
        elif args.command == 'reset':
            # Xác nhận trước khi reset
            confirm = input("⚠️ This will reset ALL system defaults. Are you sure? (y/N): ").strip().lower()
            if confirm == 'y':
                success = await cli_manager.reset_system()
            else:
                print("❌ Reset cancelled!")
                success = True
                
        elif args.command == 'health':
            success = await cli_manager.check_health()
            
        elif args.command == 'interactive':
            await cli_manager.interactive_menu()
            success = True
            
        else:
            parser.print_help()
            success = False
            
        # Cleanup
        await cli_manager.cleanup()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("⚠️ Operation cancelled by user")
        await cli_manager.cleanup()
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        await cli_manager.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
