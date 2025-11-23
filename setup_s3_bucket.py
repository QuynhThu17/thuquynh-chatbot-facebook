"""
Script để setup S3 bucket cho public access
Chỉ cần chạy 1 lần
"""

import boto3
import json
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_s3_bucket():
    """Setup S3 bucket for public access"""
    try:
        # Get credentials from environment
        AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
        AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        AWS_BUCKET_NAME = os.getenv('AWS_BUCKET_NAME')
        
        if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_BUCKET_NAME]):
            logger.error("❌ Missing AWS credentials or bucket name in environment variables")
            return False
        
        # Initialize S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_DEFAULT_REGION
        )
        
        logger.info(f"🔧 Setting up S3 bucket: {AWS_BUCKET_NAME}")
        
        # 1. Disable Block Public Access
        try:
            s3_client.delete_public_access_block(Bucket=AWS_BUCKET_NAME)
            logger.info("✅ Disabled public access block")
        except Exception as e:
            logger.warning(f"⚠️  Public access block: {str(e)}")
        
        # 2. Apply bucket policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{AWS_BUCKET_NAME}/*"
                }
            ]
        }
        
        s3_client.put_bucket_policy(
            Bucket=AWS_BUCKET_NAME,
            Policy=json.dumps(bucket_policy)
        )
        logger.info("✅ Applied bucket policy for public read access")
        
        # 3. Test upload a small file
        test_key = "test-public-access.txt"
        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=test_key,
            Body=b"Test public access",
            ContentType="text/plain"
        )
        
        test_url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_DEFAULT_REGION}.amazonaws.com/{test_key}"
        logger.info(f"✅ Test file uploaded: {test_url}")
        
        # Clean up test file
        s3_client.delete_object(Bucket=AWS_BUCKET_NAME, Key=test_key)
        logger.info("✅ Test file cleaned up")
        
        logger.info("🎉 S3 bucket setup completed successfully!")
        logger.info(f"📦 Bucket: {AWS_BUCKET_NAME}")
        logger.info("🌐 Files uploaded to this bucket will now be publicly accessible")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    setup_s3_bucket()
