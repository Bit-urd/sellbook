"""
店铺模型
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Shop:
    """店铺模型"""
    id: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    contact: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def __repr__(self):
        return f"Shop(id='{self.id}', name='{self.name}')"