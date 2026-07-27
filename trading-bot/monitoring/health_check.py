import os
import time
import logging
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from data.database import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthMonitor:
    """Monitor the health of the trading bot"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
    def check_database_health(self):
        """Check if database is accessible"""
        try:
            with self.db.get_session() as session:
                from data.database import PriceData
                from sqlalchemy import func
                
                latest = session.query(
                    func.max(PriceData.timestamp)
                ).scalar()
                
                if latest:
                    time_diff = (datetime.now() - latest).total_seconds()
                    if time_diff > 3600:
                        logger.warning(f"Price data is {time_diff/60:.1f} minutes old")
                        return False, f"Stale data: {time_diff/60:.1f} min"
                    return True, "Database healthy"
                else:
                    return False, "No price data"
                    
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return False, str(e)
    
    def check_trading_status(self):
        """Check if bot is active"""
        try:
            with self.db.get_session() as session:
                from data.database import Portfolio
                from sqlalchemy import func
                
                latest = session.query(
                    func.max(Portfolio.timestamp)
                ).scalar()
                
                if latest:
                    time_diff = (datetime.now() - latest).total_seconds()
                    if time_diff > 7200:
                        logger.warning(f"No activity for {time_diff/3600:.1f} hours")
                        return False, f"Inactive: {time_diff/3600:.1f} hrs"
                    return True, "Trading active"
                else:
                    return False, "No trading history"
                    
        except Exception as e:
            logger.error(f"Trading check failed: {e}")
            return False, str(e)
    
    def run_health_check(self):
        """Run all health checks"""
        logger.info("Starting health check...")
        
        checks = {
            'Database': self.check_database_health(),
            'Trading': self.check_trading_status()
        }
        
        all_healthy = True
        
        for name, (healthy, message) in checks.items():
            status = "✓" if healthy else "✗"
            logger.info(f"{status} {name}: {message}")
            
            if not healthy:
                all_healthy = False
        
        if all_healthy:
            logger.info("All systems healthy ✓")
        else:
            logger.warning("System health issues detected")
        
        return all_healthy

def main():
    """Run health check"""
    monitor = HealthMonitor()
    healthy = monitor.run_health_check()
    return 0 if healthy else 1

if __name__ == "__main__":
    exit(main())