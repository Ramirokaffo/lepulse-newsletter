from collections import Counter
from datetime import timedelta

from django.utils import timezone


def activity_series(events, days=14):
    start = timezone.localdate() - timedelta(days=days - 1)
    counters = {'open': Counter(), 'click': Counter()}
    for event_type, created_at in events.filter(created_at__date__gte=start).values_list(
        'event_type', 'created_at'
    ):
        counters[event_type][timezone.localtime(created_at).date()] += 1
    maximum = max((max(values.values(), default=0) for values in counters.values()), default=0)
    maximum = maximum or 1
    return [
        {
            'label': (start + timedelta(days=index)).strftime('%d/%m'),
            'opens': counters['open'][start + timedelta(days=index)],
            'clicks': counters['click'][start + timedelta(days=index)],
            'open_width': round(counters['open'][start + timedelta(days=index)] * 100 / maximum),
            'click_width': round(counters['click'][start + timedelta(days=index)] * 100 / maximum),
        }
        for index in range(days)
    ]