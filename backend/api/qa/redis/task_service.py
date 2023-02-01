import json
from django.core.cache import cache

# Taskservice class to handle tasks
class TaskService:
    user_uuid = None
    running_task = []

    def __init__(self, User_uuid) -> None:
        self.user_uuid = User_uuid
        if cache.get(str(self.user_uuid)) == None:
            cache.set(str(self.user_uuid), json.dumps([]))
        else:
            self.running_task = json.loads(cache.get(str(self.user_uuid)))
        pass

    # ADD Running Tasks
    def AddRunningTasks(self, task):
        self.running_task.append(task)
        cache.set(str(self.user_uuid), json.dumps(self.running_task))
        return task.task_id

    # GET Running Tasks
    def getRunningTasks(self):
        return json.loads(cache.get(str(self.user_uuid)))

    # DELETE Running Tasks
    def deleteRunningTasks(self, uuid):
        for task in self.running_task:
            if task["task_id"] == uuid:
                self.running_task.remove(task)
                cache.set(str(self.user_uuid), json.dumps(self.running_task))
                break
        pass
