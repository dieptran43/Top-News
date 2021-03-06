# -*- coding: utf-8 -*-

'''
Time decay model:
If selected:
p = (1-α)p + α
If not:
p = (1-α)p
Where p is the selection probability, and α is the degree of weight decrease.
The result of this is that the nth most recent selection will have a weight of
(1-α)^n. Using a coefficient value of 0.05 as an example, the 10th most recent
selection would only have half the weight of the most recent. Increasing epsilon
would bias towards more recent results more.
'''

import news_recommendation_service.news_classes as news_classes
import os
import sys

# import common package in parent directory
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'common'))

import common.mongodb_client as mongodb_client
from common.cloudAMQP_client import CloudAMQPClient

# Don't modify this value unless you know what you are doing.
NUM_OF_CLASSES = 14
INITIAL_P = 1.0 / NUM_OF_CLASSES
ALPHA = 0.2

SLEEP_TIME_IN_SECONDS = 1

LOG_CLICKS_TASK_QUEUE_URL = "amqp://lznzxucj:TMLwAMQoQ8MHAL_Srf76wLyo1fGsCdP2@woodpecker.rmq.cloudamqp.com/lznzxucj"
LOG_CLICKS_TASK_QUEUE_NAME = "tap-news-log-clicks-task-queue"

PREFERENCE_MODEL_TABLE_NAME = "user_preference_model"
NEWS_TABLE_NAME = "news"

cloudAMQP_client = CloudAMQPClient(LOG_CLICKS_TASK_QUEUE_URL, LOG_CLICKS_TASK_QUEUE_NAME)


def handle_message(msg):
    if msg is None or not isinstance(msg, dict):
        return

    if ('userId' not in msg
            or 'newsId' not in msg
            or 'timestamp' not in msg):
        return

    userId = msg['userId']
    newsId = msg['newsId']
    print('newsid', newsId)
    # Update user's preference
    db = mongodb_client.get_db()
    model = db[PREFERENCE_MODEL_TABLE_NAME].find_one({'userId': userId})

    # If model not exists, create a new one
    if model is None:
        print('Creating preference model for new user: %s' % userId)
        new_model = {'userId': userId}
        # preference map for each topic
        preference = {}
        for i in news_classes.classes:
            preference[i] = float(INITIAL_P)
        new_model['preference'] = preference
        model = new_model

    print('Updating preference model for new user: %s' % userId)

    # Update model using time decaying method
    news = db[NEWS_TABLE_NAME].find_one({'digest': newsId})
    print(news)
    if (news is None
            or 'class' not in news
            or news['class'] not in news_classes.classes):
        # print(news is None)
        # print('class' not in news)
        # print(news['class'] not in news_classes.classes)
        # print('Skipping processing...')
        return

    click_class = news['class']

    # Update the clicked topic
    old_p = model['preference'][click_class]
    model['preference'][click_class] = float((1 - ALPHA) * old_p + ALPHA)

    # Update not clicked classes.
    for i, prob in model['preference'].items():
        if not i == click_class:
            model['preference'][i] = float((1 - ALPHA) * model['preference'][i])

    print("model", model)
    db[PREFERENCE_MODEL_TABLE_NAME].replace_one({'userId': userId}, model, upsert=True)


def run():
    while True:
        if cloudAMQP_client is not None:
            msg = cloudAMQP_client.get_message()
            print(msg)
            if msg is not None:
                # Parse and process the task
                try:
                    handle_message(msg)
                except Exception as e:
                    print(e)
                    pass
            # Remove this if this becomes a bottleneck.
            cloudAMQP_client.sleep(SLEEP_TIME_IN_SECONDS)


if __name__ == "__main__":
    run()
