import json
import random
import numpy as np
import argparse
import os
from datetime import datetime
from pathlib import Path

def parse_arguments():
    parser = argparse.ArgumentParser(description='Email System IDS')
    parser.add_argument('events_file', help='Path to Events.txt')
    parser.add_argument('stats_file', help='Path to Stats.txt')
    parser.add_argument('days', type=int, help='Number of days to simulate')
    return parser.parse_args()

def ensure_directories():
    """Create necessary directories for logs and analysis results"""
    Path("logs/baseline").mkdir(parents=True, exist_ok=True)
    Path("logs/monitoring").mkdir(parents=True, exist_ok=True)
    Path("analysis").mkdir(exist_ok=True)

def parse_events(file_path):
    """Parse Events.txt with error handling"""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            event_count = int(lines[0].strip())
            events = {}
            for line in lines[1:]:
                name, event_type, min_val, max_val, weight = line.strip().split(":")[:5]
                events[name] = {
                    "type": event_type,
                    "min": float(min_val) if min_val else None,
                    "max": float(max_val) if max_val else None,
                    "weight": int(weight)
                }
            if len(events) != event_count:
                print(f"Warning: Expected {event_count} events but found {len(events)}")
            return events
    except Exception as e:
        print(f"Error parsing Events file: {e}")
        raise

def parse_stats(file_path):
    """Parse Stats.txt with error handling"""
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            event_count = int(lines[0].strip())
            stats = {}
            for line in lines[1:]:
                name, mean, std_dev = line.strip().split(":")[:3]
                stats[name] = {
                    "mean": float(mean),
                    "std_dev": float(std_dev)
                }
            if len(stats) != event_count:
                print(f"Warning: Expected {event_count} events but found {len(stats)}")
            return stats
    except Exception as e:
        print(f"Error parsing Stats file: {e}")
        raise

def validate_configuration(events, stats):
    """Validate consistency between Events.txt and Stats.txt"""
    if set(events.keys()) != set(stats.keys()):
        missing = set(events.keys()) ^ set(stats.keys())
        raise ValueError(f"Inconsistent events between files. Mismatched events: {missing}")
    
    for event_name, event_data in events.items():
        stat_data = stats[event_name]
        if event_data["type"] == "D" and not (isinstance(stat_data["mean"], (int, float))):
            print(f"Warning: Discrete event {event_name} has non-integer mean")

def write_daily_log(day, events, phase="baseline"):
    """Write daily events to log file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"logs/{phase}/day_{day}_{timestamp}.json"
    with open(log_path, 'w') as f:
        json.dump(events, f, indent=2)
    return log_path

def write_analysis_results(stats, filename):
    """Write analysis results to file"""
    filepath = f"analysis/{filename}"
    with open(filepath, 'w') as f:
        json.dump(stats, f, indent=2)
    return filepath

def generate_daily_events(events, stats, days=1, phase="baseline"):
    """Generate daily events with progress feedback"""
    log_data = []
    print(f"\nGenerating events for {days} days ({phase} phase)...")
    
    for day in range(days):
        if day % 5 == 0 or day == days - 1:
            print(f"Progress: {day + 1}/{days} days processed")
            
        daily_events = {}
        for event, params in events.items():
            if params["type"] == "D":  # Discrete event
                daily_value = int(np.random.normal(stats[event]["mean"], stats[event]["std_dev"]))
                if params["min"] is not None:
                    daily_value = max(daily_value, int(params["min"]))
                if params["max"] is not None:
                    daily_value = min(daily_value, int(params["max"]))
            else:  # Continuous event
                daily_value = round(np.random.normal(stats[event]["mean"], stats[event]["std_dev"]), 2)
                if params["min"] is not None:
                    daily_value = max(daily_value, params["min"])
                if params["max"] is not None:
                    daily_value = min(daily_value, params["max"])
            daily_events[event] = daily_value
            
        log_path = write_daily_log(day + 1, daily_events, phase)
        log_data.append(daily_events)
        
    return log_data

def calculate_statistics(log_data):
    """Calculate statistics from log data"""
    stats_summary = {}
    for event in log_data[0].keys():
        event_values = [day[event] for day in log_data]
        mean_val = np.mean(event_values)
        std_dev_val = np.std(event_values)
        stats_summary[event] = {
            "mean": float(mean_val),
            "std_dev": float(std_dev_val)
        }
    return stats_summary

def detect_anomalies(baseline_stats, events, log_data):
    """Detect anomalies in log data"""
    threshold = 2 * sum(event["weight"] for event in events.values())
    alerts = []

    print(f"\nAnomaly detection threshold: {threshold:.2f}")
    
    for day, data in enumerate(log_data, 1):
        anomaly_counter = 0
        daily_deviations = {}
        
        for event, value in data.items():
            deviation = abs(value - baseline_stats[event]["mean"]) / baseline_stats[event]["std_dev"]
            weighted_deviation = deviation * events[event]["weight"]
            anomaly_counter += weighted_deviation
            daily_deviations[event] = weighted_deviation

        is_alert = anomaly_counter >= threshold
        alert_data = {
            "day": day,
            "anomaly_counter": round(anomaly_counter, 2),
            "threshold": threshold,
            "alert": is_alert,
            "status": "ALERT" if is_alert else "OK",
            "deviations": daily_deviations
        }
        alerts.append(alert_data)
        
    return alerts

def run_baseline_phase(events, stats, days):
    """Run baseline data collection phase"""
    print("\nStarting baseline phase...")
    baseline_data = generate_daily_events(events, stats, days, "baseline")
    baseline_stats = calculate_statistics(baseline_data)
    stats_file = write_analysis_results(baseline_stats, "baseline_stats.json")
    print(f"Baseline statistics written to {stats_file}")
    return baseline_stats

def run_monitoring_phase(events, baseline_stats, days):
    """Run monitoring phase"""
    while True:
        try:
            stats_file = input("\nEnter path to new statistics file (or 'quit' to exit): ")
            if stats_file.lower() == 'quit':
                break
                
            new_stats = parse_stats(stats_file)
            validate_configuration(events, new_stats)
            
            print("\nStarting monitoring phase...")
            live_data = generate_daily_events(events, new_stats, days, "monitoring")
            alerts = detect_anomalies(baseline_stats, events, live_data)
            
            # Write alerts to file and display results
            alert_file = write_analysis_results(alerts, f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            print(f"\nAlert results written to {alert_file}")
            
            print("\nDaily Status Report:")
            for alert in alerts:
                print(f"\nDay {alert['day']}: Anomaly Counter = {alert['anomaly_counter']:.2f}, "
                      f"Status = {alert['status']}")
                if alert['alert']:
                    print("  Significant deviations in events:")
                    for event, deviation in alert['deviations'].items():
                        if deviation > 1.0:
                            print(f"    - {event}: {deviation:.2f} standard deviations")
            
        except Exception as e:
            print(f"Error during monitoring phase: {e}")
            print("Please try again with a valid statistics file.")

def main():
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Ensure necessary directories exist
        ensure_directories()
        
        # Load and validate initial configuration
        print("\nLoading configuration...")
        events = parse_events(args.events_file)
        initial_stats = parse_stats(args.stats_file)
        validate_configuration(events, initial_stats)
        
        print(f"\nConfiguration loaded successfully:")
        print(f"- Number of events: {len(events)}")
        print(f"- Events being monitored: {', '.join(events.keys())}")
        
        # Run baseline phase
        baseline_stats = run_baseline_phase(events, initial_stats, args.days)
        
        # Run monitoring phase
        run_monitoring_phase(events, baseline_stats, args.days)
        
    except Exception as e:
        print(f"\nError in main execution: {e}")
        return 1
        
    print("\nProgram completed successfully.")
    return 0

if __name__ == "__main__":
    exit(main())