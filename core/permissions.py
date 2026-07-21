from django.contrib.auth.decorators import user_passes_test


staff_required = user_passes_test(lambda user: user.is_authenticated and user.is_staff)
administrator_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff and user.is_administrator
)