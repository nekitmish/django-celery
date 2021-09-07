from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from freezegun import freeze_time
from mixer.backend.django import mixer

from elk.utils.testing import ClassIntegrationTestCase, create_customer, create_teacher
from market.models import Subscription
from market.tasks import remind_weekly_truants
from products.models import Product1


@freeze_time('2032-12-01 12:00')
class TestNotificationUnusedSubscription(ClassIntegrationTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product1.objects.get(pk=1)
        cls.product.duration = timedelta(days=42)
        cls.product.save()

        cls.customer = create_customer()

    def setUp(self):
        self.s = Subscription(
            customer=self.customer,
            product=self.product,
            buy_price=150
        )
        self.s.save()

    @patch('market.models.signals.class_scheduled.send')
    def _schedule(self, c, date, *args):
        c.timeline = mixer.blend(
            'timeline.Entry',
            lesson_type=c.lesson_type,
            teacher=create_teacher(),
            start=date,
        )
        c.save()

    def test_remind_weekly_truants(self):
        with freeze_time('2032-12-08 12:00'):
            self.assertTrue(self.s.need_remind)
            remind_weekly_truants()
            self.s.refresh_from_db()
            self.assertFalse(self.s.need_remind)
            self.assertEqual(len(mail.outbox), 1)

            out_emails = [outbox.to[0] for outbox in mail.outbox]

            self.assertIn(self.customer.user.email, out_emails)

    def test_not_send_reminder_if_planned_class(self):
        cls = self.s.classes.first()
        self._schedule(cls, self.tzdatetime('UTC', 2032, 12, 15, 12, 0))
        with freeze_time('2032-12-08 12:00'):
            remind_weekly_truants()
            self.assertEqual(len(mail.outbox), 0)

    def test_not_send_reminder_if_passed_class_6_days_ago(self):
        cls = self.s.classes.first()
        self._schedule(cls, self.tzdatetime('UTC', 2032, 12, 2, 12, 0))
        with freeze_time('2032-12-08 12:00'):
            remind_weekly_truants()
            self.assertEqual(len(mail.outbox), 0)

    def test_send_reminder_if_passed_class_7_days_ago(self):
        cls = self.s.classes.first()
        self._schedule(cls, self.tzdatetime('UTC', 2032, 12, 2, 12, 0))
        with freeze_time('2032-12-09 12:00'):
            remind_weekly_truants()
            self.assertEqual(len(mail.outbox), 1)

    def test_do_not_repeat_reminder(self):
        with freeze_time('2032-12-08 12:00'):
            for i in range(10):
                remind_weekly_truants()
            self.assertEqual(len(mail.outbox), 1)
