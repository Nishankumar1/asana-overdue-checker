import os
import requests
from datetime import datetime, timezone

ASANA_PAT = os.getenv('ASANA_PAT')
PROJECT_GID = os.getenv('ASANA_PROJECT_GID')
CUSTOM_FIELD_GID = os.getenv('CUSTOM_FIELD_GID') 
OVERDUE_OPTION_GID = os.getenv('OVERDUE_OPTION_GID')

if not all([ASANA_PAT, PROJECT_GID, CUSTOM_FIELD_GID, OVERDUE_OPTION_GID]):
    print("Error: Ensure ASANA_PAT, PROJECT_GID, CUSTOM_FIELD_GID, and OVERDUE_OPTION_GID are set.")
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

def set_task_progress_to_overdue(task_gid):
    """Updates the custom field of a task to the 'Overdue' status."""
    update_url = f"https://app.asana.com/api/1.0/tasks/{task_gid}"
    payload = {
        "data": {
            "custom_fields": {
                CUSTOM_FIELD_GID: OVERDUE_OPTION_GID
            }
        }
    }
    response = requests.put(update_url, headers=HEADERS, json=payload)
    response.raise_for_status()
    print(f"  - Set 'Task Progress' to Overdue for task GID {task_gid}.")

def main():
    """Main function to fetch and process tasks."""
    print("Starting Asana overdue task check...")
    
    params = {
        "completed_since": "now",
        "opt_fields": "name,due_on,completed,num_subtasks,custom_fields"
    }
    
    try:
        response = requests.get(TASKS_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        tasks = response.json()['data']
        
        print(f"Found {len(tasks)} non-completed tasks to check.")
        
        for task in tasks:
            task_gid = task['gid']
            task_name = task['name']
            
            is_already_overdue = False
            for field in task['custom_fields']:
                if field['gid'] == CUSTOM_FIELD_GID and field.get('enum_value', {}).get('gid') == OVERDUE_OPTION_GID:
                    is_already_overdue = True
                    break
            
            if is_already_overdue:
                continue

            parent_overdue = is_task_overdue(task.get('due_on'))
            subtask_overdue = False

            if not parent_overdue and task['num_subtasks'] > 0:
                print(f"-> Checking subtasks for '{task_name}'...")
                subtasks = get_subtasks(task_gid)
                for subtask in subtasks:
                    if not subtask['completed'] and is_task_overdue(subtask.get('due_on')):
                        print(f"  - Found overdue subtask: '{subtask['name']}'")
                        subtask_overdue = True
                        break
            
            if parent_overdue or subtask_overdue:
                print(f"-> Flagging '{task_name}' by setting Custom Field to Overdue.")
                set_task_progress_to_overdue(task_gid)

    except requests.exceptions.RequestException as e:
        print(f"An API error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    print("Asana check complete.")

if __name__ == "__main__":
    main()
