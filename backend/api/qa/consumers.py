import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

# TasksConsumer class to handle tasks websocket
class TasksConsumer(WebsocketConsumer):
    group_name = "monitoring"

    # Connect function to handle websocket connection
    # adding user to group (monitoring)
    def connect(self):
        # Join group
        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)
        if self.scope["user"] == False:
            self.close(code=4001)
        self.accept()

    # Disconnect function to handle websocket disconnection
    def disconnect(self, close_code):
        # Leave group
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name, self.channel_name
        )

    # Receive message from WebSocket
    def receive(self, text_data):
        pass

    # Receive message from group (monitoring)
    def task_status(self, event):
        data = event["data"]
        # Send message to WebSocket
        self.send(
            text_data=json.dumps(
                {
                    "data": data,
                    "type": "task_status",
                }
            )
        )

    # Send Monitoring metrics to group (monitoring)
    def send_Metrics(self, event):
        data = event["data"]
        # Send message to WebSocket
        self.send(
            text_data=json.dumps(
                {
                    "data": data,
                    "type": "send_Metrics",
                }
            )
        )
