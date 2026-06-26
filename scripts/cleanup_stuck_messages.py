#!/usr/bin/env python3
"""
Cleanup Stuck Messages Script

Finds deliveries stuck in 'formatting' state for > 10 minutes and resets them to 'queued' state.
This helps recover from situations where LLM formatting was interrupted or failed.
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.db_manager import DatabaseManager
from src.database.repositories import DeliveryRepository
from src.core.state_machine import DeliveryState
import json

def cleanup_stuck_messages():
    """Find and reset stuck deliveries"""
    # Initialize database (use relative path like the server does)
    db_path = Path(__file__).parent.parent / "database" / "notify.db"
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 1
    
    # Use relative path format
    db_uri = f"sqlite3:///./database/notify.db"
    db = DatabaseManager(db_uri)
    delivery_repo = DeliveryRepository(db)
    
    # Find deliveries stuck in formatting state
    stuck_threshold = datetime.now() - timedelta(minutes=10)
    
    # Get all formatting deliveries
    formatting_deliveries = delivery_repo.list(state=DeliveryState.FORMATTING.value, limit=1000)
    
    stuck_count = 0
    reset_count = 0
    
    print(f"🔍 Checking {len(formatting_deliveries)} deliveries in 'formatting' state...")
    
    for delivery in formatting_deliveries:
        delivery_id = delivery['id']
        updated_at_str = delivery.get('updated_at')
        
        if not updated_at_str:
            # No updated_at, consider it stuck
            stuck_count += 1
            print(f"  ⚠️  Delivery {delivery_id}: No updated_at timestamp")
        else:
            try:
                # Parse updated_at (SQLite format: YYYY-MM-DD HH:MM:SS)
                updated_at = datetime.strptime(updated_at_str, "%Y-%m-%d %H:%M:%S")
                if updated_at < stuck_threshold:
                    stuck_count += 1
                    age_minutes = (datetime.now() - updated_at).total_seconds() / 60
                    print(f"  ⚠️  Delivery {delivery_id}: Stuck for {age_minutes:.1f} minutes (updated: {updated_at_str})")
            except Exception as e:
                print(f"  ⚠️  Delivery {delivery_id}: Error parsing updated_at '{updated_at_str}': {e}")
                stuck_count += 1
        
        if stuck_count > 0:
            # Reset to queued state
            try:
                delivery_repo.update_state(
                    delivery_id=delivery_id,
                    state=DeliveryState.QUEUED.value,
                )
                
                # Clear LLM retry metadata
                metadata = delivery.get("metadata_json")
                if metadata:
                    try:
                        metadata_dict = json.loads(metadata)
                        metadata_dict.pop('llm_retry_after', None)
                        metadata_dict.pop('llm_queue_length', None)
                        metadata_dict.pop('llm_wait_time', None)
                        delivery_repo.update_metadata(
                            delivery_id=delivery_id,
                            metadata_json=json.dumps(metadata_dict),
                        )
                    except:
                        pass
                
                reset_count += 1
                print(f"  ✅ Delivery {delivery_id}: Reset to 'queued' state")
            except Exception as e:
                print(f"  ❌ Delivery {delivery_id}: Failed to reset: {e}")
    
    print(f"\n📊 Summary:")
    print(f"  - Stuck deliveries found: {stuck_count}")
    print(f"  - Deliveries reset: {reset_count}")
    
    if reset_count > 0:
        print(f"\n✅ Cleanup completed: {reset_count} delivery(ies) reset to 'queued' state")
    else:
        print(f"\n✅ No stuck deliveries found")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = cleanup_stuck_messages()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        sys.exit(1)

