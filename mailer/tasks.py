from datetime import timedelta

from django.db.models import Q, Count
from django.utils import timezone

from elk.celery import app as celery
from market.models import Class, Subscription
from timeline.signals import skips_classes_student


@celery.task
def send_email(owl):
    owl.msg.send()


@celery.task
def send_reminder_to_weekly_truants():
    """
    Method for sending reminders to students who have not studied by subscription for more than a week

    In this implementation, the reminder is sent only once.

    In the first part of the method, we send a reminder to students who had their last class more than a week ago
    and do not have any scheduled classes.
    """

    week_ago = timezone.now() - timedelta(days=7)

    for c in Class.objects.filter(subscription__need_remind=True,
                                  subscription__is_fully_used=False,
                                  is_scheduled=True,
                                  timeline__isnull=False,
                                  timeline__end__lte=week_ago).order_by("timeline__end"):

        if not c.subscription.is_due() and (c.customer.classes.filter(
        is_scheduled=True, timeline__isnull=False).order_by("timeline__end").last()) == c:
            skips_classes_student.send(sender=send_reminder_to_weekly_truants, instance=c)
            c.subscription.need_remind = False
            c.subscription.save()

    """
    In this part of the method, we send a reminder to students who bought a subscription more than a week ago,
    but did not take or schedule any class.
    """

    for subscription in Subscription.objects.annotate(
        planned_classes=Count('classes', filter=Q(classes__is_scheduled=True, classes__timeline__isnull=False))).\
        filter(planned_classes=0, buy_date__lte=week_ago, first_lesson_date__isnull=True, need_remind=True):

        if not subscription.is_due():
            skips_classes_student.send(sender=send_reminder_to_weekly_truants, instance=subscription)
            subscription.need_remind = False
            subscription.save()
