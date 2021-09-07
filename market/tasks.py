from elk.celery import app as celery
from market.models import Subscription
from timeline.signals import skips_classes_student


@celery.task
def remind_weekly_truants():
    for s in Subscription.objects.not_used_for_a_week().filter(need_remind=True):
        skips_classes_student.send(sender=remind_weekly_truants, instance=s)
        s.not_need_remind()
