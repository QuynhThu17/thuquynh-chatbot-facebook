"""
Storage Services
Module chứa các services cho storage (S3, local, etc.)
"""

from .s3_service import S3Service

__all__ = [
    'S3Service'
]
