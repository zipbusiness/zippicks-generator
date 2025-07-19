"""
Monitor - Tracks generation progress and manages the generation queue
"""

import json
import fcntl
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict
import yaml


class GenerationMonitor:
    """Tracks what has been generated and manages the queue"""
    
    def __init__(self):
        self.log_file = Path("output/logs/generation_log.json")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load configurations
        self.cities = self._load_cities()
        self.vibes = self._load_vibes()
        
        # Load generation log
        self.log = self._load_log()
    
    def _load_cities(self) -> List[str]:
        """Load city list from config"""
        cities_file = Path("config/cities.yaml")
        
        if not cities_file.exists():
            return ['san-francisco', 'new-york', 'los-angeles']
        
        with open(cities_file, 'r') as f:
            data = yaml.safe_load(f)
            return list(data.get('cities', {}).keys())
    
    def _load_vibes(self) -> List[str]:
        """Load vibe list from config"""
        vibes_file = Path("config/vibes.yaml")
        
        if not vibes_file.exists():
            return ['date-night', 'family-friendly', 'quick-lunch']
        
        with open(vibes_file, 'r') as f:
            data = yaml.safe_load(f)
            return list(data.get('vibes', {}).keys())
    
    def _load_log(self) -> Dict:
        """Load generation log with file locking"""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                try:
                    # Acquire shared lock for reading
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    data = json.load(f)
                    return data
                finally:
                    # Release lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        
        return {
            'generated': {},
            'failed': {},
            'in_progress': {},
            'stats': {
                'total_generated': 0,
                'total_failed': 0,
                'last_updated': None
            }
        }
    
    def _save_log(self):
        """Save generation log with file locking"""
        self.log['stats']['last_updated'] = datetime.now().isoformat()
        
        # Ensure directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.log_file, 'w') as f:
            try:
                # Acquire exclusive lock for writing
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(self.log, f, indent=2)
            finally:
                # Release lock
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def mark_as_generated(self, city: str, vibe: str):
        """Mark a city/vibe combination as generated"""
        
        if city not in self.log['generated']:
            self.log['generated'][city] = {}
        
        self.log['generated'][city][vibe] = {
            'timestamp': datetime.now().isoformat(),
            'status': 'completed'
        }
        
        # Remove from in_progress if present
        if city in self.log['in_progress'] and vibe in self.log['in_progress'][city]:
            del self.log['in_progress'][city][vibe]
        
        # Update stats
        self.log['stats']['total_generated'] += 1
        
        self._save_log()
    
    def mark_as_failed(self, city: str, vibe: str, error: str):
        """Mark a city/vibe combination as failed"""
        
        if city not in self.log['failed']:
            self.log['failed'][city] = {}
        
        self.log['failed'][city][vibe] = {
            'timestamp': datetime.now().isoformat(),
            'error': error,
            'attempts': self.log['failed'].get(city, {}).get(vibe, {}).get('attempts', 0) + 1
        }
        
        # Remove from in_progress if present
        if city in self.log['in_progress'] and vibe in self.log['in_progress'][city]:
            del self.log['in_progress'][city][vibe]
        
        # Update stats
        self.log['stats']['total_failed'] += 1
        
        self._save_log()
    
    def mark_as_in_progress(self, city: str, vibe: str):
        """Mark a city/vibe combination as in progress"""
        
        if city not in self.log['in_progress']:
            self.log['in_progress'][city] = {}
        
        self.log['in_progress'][city][vibe] = {
            'timestamp': datetime.now().isoformat()
        }
        
        self._save_log()
    
    def is_generated(self, city: str, vibe: str) -> bool:
        """Check if a city/vibe combination has been generated"""
        return city in self.log['generated'] and vibe in self.log['generated'][city]
    
    def get_all_combinations(self) -> List[Tuple[str, str]]:
        """Get all possible city/vibe combinations"""
        combinations = []
        
        for city in self.cities:
            for vibe in self.vibes:
                combinations.append((city, vibe))
        
        return combinations
    
    def get_remaining_combinations(self) -> List[Tuple[str, str]]:
        """Get combinations that haven't been generated yet"""
        remaining = []
        
        for city, vibe in self.get_all_combinations():
            if not self.is_generated(city, vibe):
                remaining.append((city, vibe))
        
        return remaining
    
    def get_todays_targets(self, limit: int = 5) -> List[Tuple[str, str]]:
        """Get next targets for generation"""
        
        # Priority order:
        # 1. Failed attempts (retry)
        # 2. Never attempted
        # 3. In progress (stale)
        
        targets = []
        
        # First, add failed attempts (up to 3 retries)
        for city in self.log.get('failed', {}):
            for vibe, data in self.log['failed'][city].items():
                if data.get('attempts', 0) < 3:
                    targets.append((city, vibe))
                    if len(targets) >= limit:
                        return targets
        
        # Then add new combinations
        for city, vibe in self.get_remaining_combinations():
            if city not in self.log.get('failed', {}) or vibe not in self.log['failed'][city]:
                targets.append((city, vibe))
                if len(targets) >= limit:
                    return targets
        
        # Finally, check stale in-progress (older than 1 hour)
        one_hour_ago = datetime.now().timestamp() - 3600
        
        for city in self.log.get('in_progress', {}):
            for vibe, data in self.log['in_progress'][city].items():
                timestamp = datetime.fromisoformat(data['timestamp']).timestamp()
                if timestamp < one_hour_ago:
                    targets.append((city, vibe))
                    if len(targets) >= limit:
                        return targets
        
        return targets
    
    def get_status(self) -> Dict:
        """Get generation status summary"""
        
        total_combinations = len(self.cities) * len(self.vibes)
        generated_count = sum(len(vibes) for vibes in self.log['generated'].values())
        
        status = {
            'total_combinations': total_combinations,
            'generated_count': generated_count,
            'failed_count': sum(len(vibes) for vibes in self.log['failed'].values()),
            'in_progress_count': sum(len(vibes) for vibes in self.log['in_progress'].values()),
            'remaining_count': total_combinations - generated_count,
            'generated_percentage': (generated_count / total_combinations * 100) if total_combinations > 0 else 0,
            'by_city': {},
            'by_vibe': {},
            'recent_generations': []
        }
        
        # Calculate by city
        for city in self.cities:
            city_total = len(self.vibes)
            city_generated = len(self.log['generated'].get(city, {}))
            
            status['by_city'][city] = {
                'total': city_total,
                'generated': city_generated,
                'percentage': (city_generated / city_total * 100) if city_total > 0 else 0
            }
        
        # Calculate by vibe
        for vibe in self.vibes:
            vibe_total = len(self.cities)
            vibe_generated = sum(1 for city in self.cities if self.is_generated(city, vibe))
            
            status['by_vibe'][vibe] = {
                'total': vibe_total,
                'generated': vibe_generated,
                'percentage': (vibe_generated / vibe_total * 100) if vibe_total > 0 else 0
            }
        
        # Get recent generations
        all_generations = []
        for city, vibes in self.log['generated'].items():
            for vibe, data in vibes.items():
                all_generations.append({
                    'city': city,
                    'vibe': vibe,
                    'timestamp': data['timestamp']
                })
        
        # Sort by timestamp and get most recent
        all_generations.sort(key=lambda x: x['timestamp'], reverse=True)
        status['recent_generations'] = all_generations[:10]
        
        return status
    
    def get_generation_report(self) -> str:
        """Generate a detailed report"""
        
        status = self.get_status()
        
        report = f"""
ZIPPICKS GENERATION REPORT
=========================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERALL PROGRESS
---------------
Total Combinations: {status['total_combinations']}
Generated: {status['generated_count']} ({status['generated_percentage']:.1f}%)
Failed: {status['failed_count']}
In Progress: {status['in_progress_count']}
Remaining: {status['remaining_count']}

PROGRESS BY CITY
---------------
"""
        
        for city, stats in status['by_city'].items():
            report += f"{city:20} {stats['generated']:3}/{stats['total']:3} ({stats['percentage']:5.1f}%)\n"
        
        report += "\nPROGRESS BY VIBE\n"
        report += "---------------\n"
        
        for vibe, stats in status['by_vibe'].items():
            report += f"{vibe:20} {stats['generated']:3}/{stats['total']:3} ({stats['percentage']:5.1f}%)\n"
        
        # Add failed attempts
        if self.log.get('failed'):
            report += "\nFAILED ATTEMPTS\n"
            report += "---------------\n"
            
            for city in self.log['failed']:
                for vibe, data in self.log['failed'][city].items():
                    report += f"{city}/{vibe}: {data['attempts']} attempts - {data.get('error', 'Unknown error')}\n"
        
        # Add recent generations
        if status['recent_generations']:
            report += "\nRECENT GENERATIONS\n"
            report += "-----------------\n"
            
            for gen in status['recent_generations'][:5]:
                timestamp = datetime.fromisoformat(gen['timestamp'])
                report += f"{gen['city']}/{gen['vibe']} - {timestamp.strftime('%Y-%m-%d %H:%M')}\n"
        
        return report
    
    def reset_failed(self, city: str = None, vibe: str = None):
        """Reset failed attempts"""
        
        if city and vibe:
            # Reset specific combination
            if city in self.log['failed'] and vibe in self.log['failed'][city]:
                del self.log['failed'][city][vibe]
                if not self.log['failed'][city]:
                    del self.log['failed'][city]
        elif city:
            # Reset all vibes for a city
            if city in self.log['failed']:
                del self.log['failed'][city]
        else:
            # Reset all failed
            self.log['failed'] = {}
        
        self._save_log()
    
    def export_to_csv(self, output_file: str = "generation_report.csv"):
        """Export generation status to CSV"""
        
        import csv
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(['City', 'Vibe', 'Status', 'Timestamp', 'Notes'])
            
            # Write data
            for city in self.cities:
                for vibe in self.vibes:
                    if self.is_generated(city, vibe):
                        timestamp = self.log['generated'][city][vibe]['timestamp']
                        writer.writerow([city, vibe, 'Generated', timestamp, ''])
                    elif city in self.log.get('failed', {}) and vibe in self.log['failed'][city]:
                        data = self.log['failed'][city][vibe]
                        writer.writerow([city, vibe, 'Failed', data['timestamp'], data.get('error', '')])
                    elif city in self.log.get('in_progress', {}) and vibe in self.log['in_progress'][city]:
                        timestamp = self.log['in_progress'][city][vibe]['timestamp']
                        writer.writerow([city, vibe, 'In Progress', timestamp, ''])
                    else:
                        writer.writerow([city, vibe, 'Pending', '', ''])
        
        print(f"✅ Exported to {output_file}")


if __name__ == "__main__":
    # Test monitor
    monitor = GenerationMonitor()
    
    # Get status
    status = monitor.get_status()
    print(f"Total combinations: {status['total_combinations']}")
    print(f"Generated: {status['generated_count']}")
    print(f"Remaining: {status['remaining_count']}")
    
    # Get next targets
    targets = monitor.get_todays_targets()
    print(f"\nNext targets: {targets}")
    
    # Generate report
    print(monitor.get_generation_report())