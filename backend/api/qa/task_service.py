import channels.layers
from asgiref.sync import async_to_sync

# Send_status function to send status to group (monitoring)
def Send_Status(data, **kwargs):

    group_name = "monitoring"
    channel_layer = channels.layers.get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "task_status",
            "data": data,
        },
    )


# Send_Metrics function to send metrics to group (monitoring)
def Send_Metrics(data, **kwargs):

    group_name = "monitoring"
    channel_layer = channels.layers.get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "send_Metrics",
            "data": data,
        },
    )
