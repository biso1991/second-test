import enum
import uuid

# Class of type enum for the type of the running task
class type_task(enum.Enum):
    training = 0
    preprocessing = 1


# Class Task (running Task)
class Task(dict):
    def __init__(self, task_type, project_id, training_job_id, project_name):
        self.__dict__.update(locals())
        self.task_id = uuid.uuid4().hex
        self.task_type = task_type
        self.project_id = project_id
        self.training_job_id = training_job_id
        self.project_name = project_name
        dict.__init__(
            self,
            task_id=self.task_id,
            task_type=task_type,
            project_id=project_id,
            training_job_id=training_job_id,
            project_name=project_name,
        )
        pass
