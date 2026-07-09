from django.urls import path

from .views import (
    MailAccountTestView,
    MailAccountView,
    MailSyncView,
    MessageDetailView,
    MessageListView,
    RawMessageView,
    SendView,
    StatsView,
)

urlpatterns = [
    path("messages/", MessageListView.as_view(), name="message-list"),
    path("messages/<uuid:pk>/", MessageDetailView.as_view(), name="message-detail"),
    path("messages/<uuid:pk>/raw/", RawMessageView.as_view(), name="message-raw"),
    path("send/", SendView.as_view(), name="send"),
    path("stats/", StatsView.as_view(), name="stats"),
    # Mail account (per-user IMAP/SMTP connectivity)
    path("account/", MailAccountView.as_view(), name="account"),
    path("account/test/", MailAccountTestView.as_view(), name="account-test"),
    path("account/sync/", MailSyncView.as_view(), name="account-sync"),
]
