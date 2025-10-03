
import os
import requests
from datetime import datetime, date, timezone
from dateutil import parser as dateparser
import time

ASANA_BASE = "https://app.asana.com/api/1.0"
PAT = os.getenv("ASANA_PAT")
PROJECT_GID = os.getenv("ASANA_PROJECT_GID")
DRY_RUN = os.getenv("DRY_RUN", "").lower() in ("1", "true", "yes")

if not PAT or not PROJECT_GID:
    raise SystemExit("Set ASANA_PAT and ASANA_PROJECT_GID environment variables before running.")

HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

def api_get(url, params=None):
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "5"))
            print(f"Rate limited by Asana, sleeping {retry_after}s...")
            time.sleep(retry_after)
            continue
        r.raise_for_status()
        return r.json()

def api_post(url, json_body):
    while True:
        r = requests.post(url, headers=HEADERS, json=json_body)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "5"))
            print(f"Rate limited by Asana, sleeping {retry_after}s...")
            time.sleep(retry_after)
            continue
        r.raise_for_status()
        return r.json()

def api_delete(url, json_body=None):
    while True:
        r = requests.post(url, headers=HEADERS, json=json_body) 
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "5"))
            print(f"Rate limited by Asana, sleeping {retry_after}s...")
            time.sleep(retry_after)
            continue
        r.raise_for_status()
        return r.json()

def get_project_workspace_gid(project_gid):
    url = f"{ASANA_BASE}/projects/{project_gid}"
    res = api_get(url, params={"opt_fields": "workspace.gid"})
    return res["data"]["workspace"]["gid"]

def find_or_create_tag(workspace_gid, tag_name="Overdue"):
    
    url = f"{ASANA_BASE}/workspaces/{workspace_gid}/tags"
    params = {"limit": 100, "opt_fields": "gid,name"}
    while url:
        res = api_get(url, params=params)
        for t in res.get("data", []):
            if t.get("name") == tag_name:
                return t["gid"]
       
        np = res.get("next_page")
        if np and np.get("uri"):
            url = np["uri"]
            params = None
        else:
            url = None
    
    print(f"Creating tag '{tag_name}' in workspace {workspace_gid}...")
    body = {"data": {"name": tag_name, "workspace": workspace_gid}}
    if DRY_RUN:
        print("[DRY RUN] Would create tag:", body)
        return None
    r = api_post(f"{ASANA_BASE}/tags", body)
    return r["data"]["gid"]

def list_project_tasks(project_gid):
    url = f"{ASANA_BASE}/projects/{project_gid}/tasks"
    params = {"limit": 100, "opt_fields": "gid,name,completed,tags,name"}
    tasks = []
    while True:
        res = api_get(url, params=params)
        tasks.extend(res.get("data", []))
        np = res.get("next_page")
        if np and np.get("uri"):
            url = np["uri"]
            params = None
        else:
            break
    return tasks

def get_task_tags(task_gid):
    url = f"{ASANA_BASE}/tasks/{task_gid}"
    res = api_get(url, params={"opt_fields": "tags.gid,tags.name"})
    tags = res["data"].get("tags", [])
    return {t["name"]: t["gid"] for t in tags}

def get_task_subtasks(task_gid):
    url = f"{ASANA_BASE}/tasks/{task_gid}/subtasks"
    params = {"opt_fields": "gid,name,due_on,due_at,completed", "limit": 100}
    subs = []
    while True:
        res = api_get(url, params=params)
        subs.extend(res.get("data", []))
        np = res.get("next_page")
        if np and np.get("uri"):
            url = np["uri"]
            params = None
        else:
            break
    return subs

def parse_iso_datetime(s):
    if not s:
        return None
    try:
        dt = dateparser.isoparse(s)
       
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        try:
            return dateparser.parse(s)
        except:
            return None

def subtask_is_overdue(subtask):
   
    if subtask.get("completed"):
        return False
    
    due_on = subtask.get("due_on")
    if due_on:
        try:
            d = datetime.strptime(due_on, "%Y-%m-%d").date()
            return d < date.today()
        except:
            pass
    due_at = subtask.get("due_at")
    if due_at:
        dt = parse_iso_datetime(due_at)
        if dt:
            return dt < datetime.now(timezone.utc)
    return False

def add_tag_to_task(task_gid, tag_gid):
    if DRY_RUN:
        print(f"[DRY RUN] Would add tag {tag_gid} to task {task_gid}")
        return
    url = f"{ASANA_BASE}/tasks/{task_gid}/addTag"
    body = {"data": {"tag": tag_gid}}
    api_post(url, body)

def remove_tag_from_task(task_gid, tag_gid):
    if DRY_RUN:
        print(f"[DRY RUN] Would remove tag {tag_gid} from task {task_gid}")
        return
    url = f"{ASANA_BASE}/tasks/{task_gid}/removeTag"
    body = {"data": {"tag": tag_gid}}
    api_delete(url, body)

def add_comment(task_gid, text):
    if DRY_RUN:
        print(f"[DRY RUN] Would add comment to {task_gid}: {text}")
        return
    url = f"{ASANA_BASE}/tasks/{task_gid}/stories"
    body = {"data": {"text": text}}
    api_post(url, body)

def main():
    print("Starting Asana Overdue Flagger")
    workspace_gid = get_project_workspace_gid(PROJECT_GID)
    print("Project belongs to workspace:", workspace_gid)
    tag_name = "Overdue"
    tag_gid = find_or_create_tag(workspace_gid, tag_name)
    if tag_gid is None and DRY_RUN:
        print("[DRY RUN] Tag not created (DRY_RUN). Continuing with dry-run logic.")
    tasks = list_project_tasks(PROJECT_GID)
    print(f"Found {len(tasks)} tasks in project {PROJECT_GID} (top-level & any tasks that belong to project).")
    changed = 0

    for t in tasks:
        task_gid = t["gid"]
        task_name = t.get("name", "")
       
        subtasks = get_task_subtasks(task_gid)
        if not subtasks:
            continue
        overdue_found = False
        for st in subtasks:
            if subtask_is_overdue(st):
                overdue_found = True
                break
        current_tags = get_task_tags(task_gid)
        has_tag = tag_name in current_tags

        if overdue_found and not has_tag:
            print(f"→ Parent task '{task_name}' ({task_gid}) has overdue subtasks. Adding tag and comment.")
            if tag_gid:
                add_tag_to_task(task_gid, tag_gid)
            add_comment(task_gid, f"⚠️ One or more subtasks are overdue (checked on {date.today().isoformat()}).")
            changed += 1
        elif not overdue_found and has_tag:
            print(f"→ Parent task '{task_name}' ({task_gid}) no longer has overdue subtasks. Removing tag.")
            if tag_gid:
                remove_tag_from_task(task_gid, current_tags[tag_name])
            add_comment(task_gid, f"✅ Overdue subtasks resolved (checked on {date.today().isoformat()}).")
            changed += 1
        else:
        
            pass

    print(f"Done. Actions performed (approx): {changed}")
    if DRY_RUN:
        print("DRY_RUN was enabled — no writes were actually made.")

if __name__ == "__main__":
    main()
