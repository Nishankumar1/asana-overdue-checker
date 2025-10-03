import os
import requests
from datetime import datetime, timezone

ASANA_PAT = os.getenv('ASANA_PAT')
PROJECT_GID = os.getenv('ASANA_PROJECT_GID')
OVERDUE_FLAG = "🚩 OVERDUE"

if not ASANA_PAT or not PROJECT_GID:
    print("Error: Set ASANA_PAT and ASANA_PROJECT_GID environment variables before running.")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {ASANA_PAT}",
    "Accept": "application/json"
}
TASKS_URL = f"https://app.asana.com/api/1.0/projects/{PROJECT_GID}/tasks"
TODAY = datetime.now(timezone.utc).date()

def is_task_overdue(due_date_str):
    """Checks if a task's due date string is in the past."""
    if not due_date_str:
        return False
    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    return due_date < TODAY

def get_subtasks(parent_task_gid):
    """Fetches all subtasks for a given parent task."""
    subtask_url = f"https://app.asana.com/api/1.0/tasks/{parent_task_gid}/subtasks"
    params = {"opt_fields": "name,due_on,completed"}
    response = requests.get(subtask_url, headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()['data']

def update_task_name(task_gid, new_name):
    """Updates the name of a specific task."""
    update_url = f"https://app.asana.com/api/1.0/tasks/{task_gid}"
    payload = {"data": {"name": new_name}}
    response = requests.put(update_url, headers=HEADERS, json=payload)
    response.raise_for_status()
    print(f"  - Updated task GID {task_gid} with new name: '{new_name}'")

def main():
    """Main function to fetch and process tasks."""
    print("Starting Asana overdue task check...")
    
    params = {
        "completed_since": "now",
        "opt_fields": "name,due_on,completed,num_subtasks"
    }
    
    try:
        response = requests.get(TASKS_URL, headers=HEADERS, params=params)
        response.raise_for_status() 
        tasks = response.json()['data']
        
        print(f"Found {len(tasks)} non-completed tasks to check.")
        
        for task in tasks:
            task_gid = task['gid']
            task_name = task['name']
            
            if OVERDUE_FLAG in task_name:
                continue

            parent_overdue = is_task_overdue(task.get('due_on'))
            subtask_overdue = False 

            if task['num_subtasks'] > 0:
                print(f"-> Checking subtasks for '{task_name}'...")
                subtasks = get_subtasks(task_gid)
                for subtask in subtasks:
                    if not subtask['completed'] and is_task_overdue(subtask.get('due_on')):
                        print(f"  - Found overdue subtask: '{subtask['name']}'")
                        subtask_overdue = True
                        break 
            
            if parent_overdue or subtask_overdue:
                print(f"-> Flagging '{task_name}' as overdue.")
                new_name = f"{OVERDUE_FLAG} {task_name}"
                update_task_name(task_gid, new_name)

    except requests.exceptions.RequestException as e:
        print(f"An API error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    print("Asana check complete.")

if __name__ == "__main__":
    main()