"""Mock Stripe views for feature tests.

Wire these in by swapping the app config in your test settings:

    INSTALLED_APPS[
        INSTALLED_APPS.index("oscar_stripe_sca.apps.StripeSCACheckoutConfig")
    ] = "oscar_stripe_sca.testing.MockStripeSCACheckoutConfig"

Control accept/cancel per-scenario in your behave environment.py:

    from django.conf import settings

    def before_scenario(context, scenario):
        if 'payment_cancel' in scenario.tags:
            settings.STRIPE_TESTING_OUTCOME = 'cancel'
        else:
            settings.STRIPE_TESTING_OUTCOME = 'accept'
"""

from django.conf import settings as django_settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from oscar.apps.checkout.views import PaymentDetailsView as CorePaymentDetailsView

from oscar_stripe_sca.apps import StripeSCACheckoutConfig
from oscar_stripe_sca.views import StripeSCASuccessResponseView


class MockStripePaymentDetailsView(CorePaymentDetailsView):
    """Replaces the Stripe-hosted payment page during feature tests.

    Reads ``settings.STRIPE_TESTING_OUTCOME``:

    - ``'accept'`` (default): freezes the basket and redirects to the
      preview page, exactly as Stripe would after a successful payment.
    - ``'cancel'``: freezes the basket and redirects to the cancel URL,
      which thaws it and returns to the basket summary.
    """

    def get(self, request, *args, **kwargs):
        outcome = getattr(django_settings, "STRIPE_TESTING_OUTCOME", "accept")
        basket = request.basket

        # Freeze the basket (the real Stripe facade does this in Facade.begin())
        basket.freeze()

        # Store fake session keys so handle_payment() can read and delete them.
        request.session["stripe_session_id"] = "mock-session"
        request.session["stripe_payment_intent_id"] = "mock-pi"

        if outcome == "cancel":
            return HttpResponseRedirect(
                reverse("checkout:stripe-cancel", kwargs={"basket_id": basket.id})
            )

        # accept: hand off to the preview page, just as Stripe's redirect would.
        return HttpResponseRedirect(
            reverse("checkout:stripe-preview", kwargs={"basket_id": basket.id})
        )


class MockIntent:
    def capture(self):
        # No-op: skips the real Stripe capture during tests.
        pass


class MockFacade:
    def retrieve_payment_intent(self, _pi):
        return MockIntent()


class MockStripeSuccessResponseView(StripeSCASuccessResponseView):
    """Preview / place-order view for tests — skips the real Stripe capture."""

    @property
    def facade(self):
        return MockFacade()


class MockStripeSCACheckoutConfig(StripeSCACheckoutConfig):
    """Checkout app config that wires in mock Stripe views for feature tests."""

    def ready(self):
        super().ready()
        self.payment_details_view = MockStripePaymentDetailsView
        self.stripe_success_view = MockStripeSuccessResponseView
